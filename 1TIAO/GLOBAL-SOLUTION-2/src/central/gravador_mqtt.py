"""Escuta os eventos do nó ESP32 (MQTT) e grava na tabela `eventos` do banco do projeto.

Uso: python src/central/gravador_mqtt.py   (Ctrl+C para parar)
Cada evento vira uma linha com origem 'esp32', o cluster do piloto (Largo da Concórdia) e `demonstracao: true`.
Mensagens repetidas (QoS 1 pode reentregar) não duplicam: a chave única é esp32:<nó>:<boot>:<seq>.
Ver docs/specs/2026-11-13-no-esp32-design.md §6.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import mensagens as m

CLUSTER_PILOTO = 139          # Largo da Concórdia (Av. Rangel Pestana), rank urbano 26 — notebook 03
NO_ID = m.NO_ID
BANCO = Path(__file__).resolve().parents[2] / "data" / "processed" / "seguranca_viaria.db"


def processar(con, payload: bytes, agora: datetime | None = None) -> str:
    """Grava um evento do nó. Devolve 'gravado', 'repetido' ou 'invalido: <motivo>'; nunca levanta exceção
    por causa do conteúdo da mensagem (um gravador que cai perde os eventos seguintes)."""
    try:
        d = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return f"invalido: não é JSON ({type(e).__name__})"
    erros = m.validar_evento(d)
    if erros:
        return "invalido: " + "; ".join(erros)
    ts = (agora or datetime.now(m.FUSO)).isoformat(timespec="seconds")
    chave = f"esp32:{NO_ID}:{d['boot']}:{d['seq']}"
    dados = {**d, "demonstracao": True, "no": NO_ID}
    antes = con.total_changes
    with con:
        con.execute("INSERT INTO eventos (timestamp, origem, cluster_id, tipo, valor, payload_json, chave) "
                    "VALUES (?, 'esp32', ?, ?, NULL, ?, ?) ON CONFLICT(chave) DO NOTHING",
                    (ts, CLUSTER_PILOTO, d["tipo"], json.dumps(dados, ensure_ascii=False), chave))
    return "gravado" if con.total_changes > antes else "repetido"


def rodar(caminho_db=BANCO, broker: str = "test.mosquitto.org", porta: int = 1883) -> None:
    """Loop de escuta: assina o tópico de eventos do nó (QoS 1) e grava cada mensagem."""
    import paho.mqtt.client as mqtt
    con = sqlite3.connect(caminho_db, check_same_thread=False)

    def ao_conectar(cliente, _u, _f, codigo, _p=None):
        print(f"conectado a {broker} ({codigo}); escutando {m.TOPICO_EVENTO}")
        cliente.subscribe(m.TOPICO_EVENTO, qos=1)

    def ao_receber(_c, _u, msg):
        print(datetime.now(m.FUSO).strftime("%H:%M:%S"), processar(con, msg.payload), msg.payload[:120])

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"gravador-{NO_ID}")
    cliente.on_connect, cliente.on_message = ao_conectar, ao_receber
    cliente.connect(broker, porta, keepalive=30)
    try:
        cliente.loop_forever()
    except KeyboardInterrupt:
        print("parado")
    finally:
        con.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rodar()
