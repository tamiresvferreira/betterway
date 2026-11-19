"""O nó ESP32 ao vivo para a interface (spec 2026-11-17 §3, §6): último estado retido, eventos recentes, comandos
de cenário e o laço do despacho da ambulância SIMULADA. Um objeto por servidor (st.cache_resource no app).
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime

import mensagens as m
from despacho import Despachante, despachadas_recentes

CENARIOS = {"normal": ("normal", {}), "pedestre": ("pedestre", {"faixa_ocupada": True}),
            "camera_tempo": ("pedestre", {"faixa_ocupada": True, "estendida": True}), "escola": ("escola", {}),
            "chuva": ("chuva", {"alagamento": False}), "alagamento": ("chuva", {"alagamento": True}),
            "ambulancia": ("ambulancia", {"eta_s": 40})}


def comando_cenario(nome: str) -> dict:
    modo, campos = CENARIOS[nome]
    return m.comando(modo, **campos)


class NoAoVivo:
    def __init__(self, publicar_bruto=None):
        self._publicar_bruto = publicar_bruto
        self.estado: dict | None = None
        self.estado_recebido_em: datetime | None = None
        self.eventos: deque = deque(maxlen=30)
        self.conectado = False
        self._trava = threading.Lock()

    # ------------------------------------------------------------ mensagens do nó
    def receber(self, topico: str, payload: bytes) -> None:
        try:
            d = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        with self._trava:
            if topico == m.TOPICO_ESTADO and isinstance(d, dict):
                self.estado, self.estado_recebido_em = d, datetime.now(m.FUSO)
            elif topico == m.TOPICO_EVENTO and m.validar_evento(d) == []:
                self.eventos.appendleft({**d, "recebido_em": datetime.now(m.FUSO).isoformat(timespec="seconds")})

    def publicar(self, cmd: dict) -> bool:
        if self._publicar_bruto is None:
            return False
        try:
            return bool(self._publicar_bruto(m.TOPICO_COMANDO, json.dumps(cmd, ensure_ascii=False)))
        except Exception:
            return False

    # ------------------------------------------------------------ conexão e despacho
    @classmethod
    def conectar(cls, broker: str = "test.mosquitto.org", porta: int = 1883, banco=None) -> "NoAoVivo":
        import paho.mqtt.client as mqtt
        cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"betterway-operador-{int(time.time())}")

        def publicar_bruto(topico, texto):
            info = cli.publish(topico, texto, qos=1)
            info.wait_for_publish(5)
            return info.is_published()

        no = cls(publicar_bruto)

        def ao_conectar(c, *_):
            no.conectado = True
            c.subscribe([(m.TOPICO_ESTADO, 1), (m.TOPICO_EVENTO, 1)])

        def ao_desconectar(*_):
            no.conectado = False

        cli.on_connect, cli.on_disconnect = ao_conectar, ao_desconectar
        cli.on_message = lambda c, u, msg: no.receber(msg.topic, msg.payload)
        cli.connect_async(broker, porta, keepalive=60)
        cli.loop_start()
        if banco is not None:
            threading.Thread(target=no._laco_despacho, args=(banco,), daemon=True).start()
        return no

    def _laco_despacho(self, banco) -> None:
        despachante = Despachante(self.publicar)
        con = sqlite3.connect(banco)
        while True:
            try:
                despachante.passo(despachadas_recentes(con, datetime.now(m.FUSO)))
            except sqlite3.Error:
                pass                       # tabela ainda não criada ou banco ocupado: tenta no próximo segundo
            time.sleep(1)
