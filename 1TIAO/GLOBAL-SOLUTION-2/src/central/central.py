"""Central do Via Segura SP: decide o modo do nó e manda por MQTT; grava cada troca em `alertas`.

    python src/central/central.py                 # demonstração (~5,5 min): uma "manhã" acelerada, todos os modos
    python src/central/central.py --ao-vivo       # relógio e chuva reais, visão do último minuto
    python src/central/central.py --ao-vivo --ambulancia 600 40   # + ambulância SIMULADA a 600 m, 40 km/h

Spec: docs/specs/2026-11-16-central-design.md. O que é simulado aparece como SIMULADO/SIMULADA no motivo (regra 8).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "estudo_b_risco_vida"))

import decisao as d
import fontes as f
import mensagens as m

CLUSTER_PILOTO = 139                     # Largo da Concórdia (Av. Rangel Pestana) — notebook 03
LAT, LON = -23.54183, -46.61613          # centro do grupo
VIDEO_VISAO = "cdmx_pexels_25775484"     # vídeo de demonstração da visão (notebook 07)
BANCO = Path(__file__).resolve().parents[2] / "data" / "processed" / "seguranca_viaria.db"
REENVIO_S = 30                           # sinal de vida: o nó volta ao normal após 120 s sem comando
REENVIO_AMBULANCIA_S = 10                # o eta é atualizado a cada 10 s

# ---------------------------------------------------------------- cenário de demonstração (spec §5)
DIA_DEMO = datetime(2026, 11, 18)        # quarta-feira (dia útil)
AMB_DIST_M, AMB_VEL_KMH = 600, 40        # ambulância SIMULADA: 54 s até o nó
# (início em s reais, hora do cenário, o que acontece)
TRECHOS = [(0, "06:30", "normal"), (30, "07:00", "escola"), (90, "07:40", "pedestre"), (150, "08:00", "chuva"),
           (195, "08:20", "alagamento"), (240, "08:40", "ambulancia"), (295, "09:00", "normal")]
DURACAO_DEMO_S = 325
ACELERACAO = 10                           # 1 s real = 10 s de cenário dentro de cada trecho


def entradas_demo(t: float, chuva_real: float | None, pessoas_visao: int) -> tuple[d.Entradas, str]:
    """Entradas do cenário no segundo `t` da demonstração. Usa a chuva real se ela passar do limiar; se não, SIMULADA."""
    inicio, hora, o_que = [tr for tr in TRECHOS if tr[0] <= t][-1]
    h, mi = map(int, hora.split(":"))
    quando = DIA_DEMO.replace(hour=h, minute=mi) + timedelta(seconds=(t - inicio) * ACELERACAO)
    e = dict(quando=quando)
    if o_que == "pedestre":
        e["pessoas_na_faixa"] = pessoas_visao
    elif o_que in ("chuva", "alagamento"):
        alvo = d.LIMIAR_ALAGAMENTO_MM_H if o_que == "alagamento" else d.LIMIAR_CHUVA_MM_H
        if chuva_real is not None and chuva_real >= alvo:
            e["chuva_mm_h"] = chuva_real
        else:
            e["chuva_mm_h"], e["chuva_simulada"] = (12.0 if o_que == "alagamento" else 6.0), True
    elif o_que == "ambulancia":
        eta = f.eta_ambulancia(t - inicio, AMB_DIST_M, AMB_VEL_KMH)
        if eta > 0:
            e["ambulancia_eta_s"] = eta
        elif t - inicio < AMB_DIST_M / (AMB_VEL_KMH / 3.6) + 1:
            e["ambulancia_passou"] = True        # um segundo de "fim"; depois o modo de baixo
    return d.Entradas(**e), quando.strftime("%H:%M")


# ---------------------------------------------------------------- laço
class Central:
    def __init__(self, con, publicar, risco_fn=None, agora_fn=None):
        self.con, self.publicar = con, publicar
        self.risco_fn = risco_fn or _risco_real
        self.agora_fn = agora_fn or (lambda: datetime.now(m.FUSO))
        self._chave = self._alerta = None
        self._ultimo_envio = -1e9

    def passo(self, e: d.Entradas, t_s: float) -> d.Decisao:
        r = d.decidir(e)
        chave = (r.modo, r.campos.get("alagamento"), r.campos.get("faixa_ocupada"), bool(r.campos.get("fim")))
        intervalo = REENVIO_AMBULANCIA_S if "eta_s" in r.campos else REENVIO_S
        if chave != self._chave or t_s - self._ultimo_envio >= intervalo:
            enviado = bool(self.publicar(m.comando(r.modo, **r.campos)))
            self._ultimo_envio = t_s
            if (r.modo, r.campos.get("alagamento")) != self._alerta:
                self._gravar_alerta(r, e, enviado)
                self._alerta = (r.modo, r.campos.get("alagamento"))
            self._chave = chave
        return r

    def _gravar_alerta(self, r: d.Decisao, e: d.Entradas, enviado: bool) -> None:
        try:
            rk = self.risco_fn(LAT, LON, e.quando, e.chuva_mm_h or 0.0)
            prob, nivel = float(rk["probabilidade_atropelamento_1h"]), rk["nivel"]
            motivo = f"{r.motivo} · risco {nivel} ({prob:.2%} de atropelamento em 1 h)"
        except Exception as erro:   # modelo indisponível não derruba a central
            prob, motivo = None, f"{r.motivo} · risco indisponível ({type(erro).__name__})"
        try:
            with self.con:
                self.con.execute("INSERT INTO alertas (timestamp, cluster_id, modo, motivo, risco, enviado) "
                                 "VALUES (?, ?, ?, ?, ?, ?)",
                                 (self.agora_fn().isoformat(timespec="seconds"), CLUSTER_PILOTO, r.modo, motivo, prob,
                                  int(enviado)))
        except sqlite3.Error as erro:
            print("aviso: alerta não gravado:", erro)


def _risco_real(lat, lon, quando, chuva_mm):
    from risco import risco
    return risco(lat, lon, quando, chuva_mm)


def _publicador(broker: str, porta: int):
    import paho.mqtt.client as mqtt
    cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"central-{m.NO_ID}")
    cli.connect(broker, porta, keepalive=60)
    cli.loop_start()

    def publicar(cmd: dict) -> bool:
        try:
            info = cli.publish(m.TOPICO_COMANDO, json.dumps(cmd, ensure_ascii=False), qos=1)
            info.wait_for_publish(5)
            return info.is_published()
        except Exception:
            return False
    return publicar


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Central do Via Segura SP")
    p.add_argument("--ao-vivo", action="store_true", help="relógio e chuva reais (padrão: demonstração)")
    p.add_argument("--ambulancia", nargs=2, type=float, metavar=("DIST_M", "VEL_KMH"), help="ambulância SIMULADA")
    p.add_argument("--broker", default="test.mosquitto.org")
    p.add_argument("--db", default=str(BANCO))
    a = p.parse_args(argv)
    con = sqlite3.connect(a.db)
    central = Central(con, _publicador(a.broker, 1883))
    chuva_real = f.chuva_prevista_mm_h(LAT, LON, datetime.now())
    print(f"chuva prevista agora no Largo da Concórdia (Open-Meteo): "
          f"{'sem dado' if chuva_real is None else f'{chuva_real:.1f} mm/h'}")
    ultimo = None
    t0 = time.monotonic()
    if not a.ao_vivo:
        pessoas = f.pessoas_na_faixa(con, video_id=VIDEO_VISAO)
        print(f"visão: {pessoas} registros de pessoa na faixa no vídeo de demonstração ({VIDEO_VISAO})")
    chuva_t = time.monotonic()
    while True:
        t = time.monotonic() - t0
        if a.ao_vivo:
            agora = datetime.now()
            if time.monotonic() - chuva_t > 600:
                chuva_real, chuva_t = f.chuva_prevista_mm_h(LAT, LON, agora), time.monotonic()
            amb = {}
            if a.ambulancia:
                eta = f.eta_ambulancia(t, *a.ambulancia)
                if eta > 0:
                    amb["ambulancia_eta_s"] = eta
                elif t < a.ambulancia[0] / (a.ambulancia[1] / 3.6) + 1:
                    amb["ambulancia_passou"] = True
            e = d.Entradas(quando=agora, chuva_mm_h=chuva_real,
                           pessoas_na_faixa=f.pessoas_na_faixa(con, desde=datetime.now(m.FUSO) - timedelta(minutes=1)),
                           **amb)
            hora = agora.strftime("%H:%M")
        else:
            if t > DURACAO_DEMO_S:
                break
            e, hora = entradas_demo(t, chuva_real, pessoas)
        r = central.passo(e, t)
        if (r.modo, r.campos) != ultimo:
            print(f"[{t:5.0f} s | {hora}] {r.modo:<10} {json.dumps(r.campos)}  — {r.motivo}")
            ultimo = (r.modo, r.campos)
        time.sleep(1)
    print("demonstração concluída")


if __name__ == "__main__":
    main()
