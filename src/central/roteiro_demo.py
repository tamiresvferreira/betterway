"""Roteiros que mandam modos ao nó ESP32 pelo MQTT, enquanto a central (17/11) não existe.

    python src/central/roteiro_demo.py           # demonstração (~5 min, para o vídeo)
    python src/central/roteiro_demo.py --teste   # aceitação: cobre a lista da spec §7 (~7 min)

A ambulância é SIMULADA (regra 8): o tempo de chegada (eta_s) cai a cada passo, como se ela se aproximasse.
No roteiro de teste, aperte o botão do Wokwi (1) no modo normal e (2) quando a ambulância estiver a ≤ 30 s.
"""
from __future__ import annotations

import json
import sys
import time

import mensagens as m


def _ambulancia(t0: float, etas: list[int], passo: float) -> list[tuple[float, dict]]:
    return [(t0 + i * passo, m.comando("ambulancia", eta_s=e)) for i, e in enumerate(etas)]


def roteiro(teste: bool = False) -> list[tuple[float, dict]]:
    """(segundos desde o início, comando). Um passo {"_pausa_s": N} é só espera, não é publicado."""
    if not teste:
        return [
            (0, m.comando("normal")),
            (40, m.comando("pedestre", faixa_ocupada=False)),
            (70, m.comando("pedestre", faixa_ocupada=True)),
            (100, m.comando("escola")),
            (150, m.comando("chuva", alagamento=False)),
            (180, m.comando("chuva", alagamento=True)),
            *_ambulancia(210, [60, 50, 40, 30, 20, 10, 0], 10),
            (285, m.comando("ambulancia", fim=True)),
            (300, m.comando("normal")),
        ]
    return [
        (0, m.comando("ambulancia", fim=True)),                 # "fim" sem ambulância ativa: nada pode travar
        (5, m.comando("normal")),
        (10, {"v": 1, "modo": "voo"}),                          # inválido de propósito → comando_invalido
        (20, m.comando("pedestre", faixa_ocupada=False)),
        (45, m.comando("pedestre", faixa_ocupada=True)),
        (75, m.comando("escola")),
        (110, m.comando("chuva", alagamento=False)),
        (130, m.comando("chuva", alagamento=True)),
        *_ambulancia(150, [50, 40, 30, 20, 10, 0], 10),         # aperte o botão quando eta ≤ 30
        (215, m.comando("ambulancia", fim=True)),
        (230, m.comando("normal")),                             # aperte o botão: travessia estendida
        (270, m.comando("ambulancia", eta_s=20)),               # sem "fim": termina sozinha em eta + 15 s
        (275, {"_pausa_s": 130}),                               # 120 s sem comando → nó volta ao normal
    ]


def _cliente():
    import paho.mqtt.client as mqtt
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


def publicar(passos, broker: str = "test.mosquitto.org", porta: int = 1883, dormir=time.sleep) -> int:
    """Publica os comandos em TOPICO_COMANDO (QoS 1) respeitando os tempos; devolve quantos publicou."""
    cliente = _cliente()
    cliente.connect(broker, porta, keepalive=30)
    cliente.loop_start()
    n, t_ant = 0, 0.0
    try:
        for t, c in passos:
            if "_pausa_s" in c:
                print(f"pausa de {c['_pausa_s']} s sem comandos")
                dormir(c["_pausa_s"])
                continue
            dormir(max(0.0, t - t_ant))
            t_ant = t
            cliente.publish(m.TOPICO_COMANDO, json.dumps(c, ensure_ascii=False), qos=1).wait_for_publish(5)
            n += 1
            print(f"{t:>5.0f} s  {c.get('modo')}  {json.dumps({k: v for k, v in c.items() if k not in ('v', 'id', 'ts')})}")
    finally:
        cliente.loop_stop()
        cliente.disconnect()
    return n


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("publicados:", publicar(roteiro(teste="--teste" in sys.argv)))
