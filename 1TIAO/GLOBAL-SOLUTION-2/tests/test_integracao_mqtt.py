"""Integração com o broker MQTT público (precisa de internet): python -m pytest tests/test_integracao_mqtt.py -m slow"""
import json
import threading
import uuid

import pytest

import mensagens as m
import roteiro_demo as r


@pytest.mark.slow
def test_comando_publicado_chega_ao_assinante(monkeypatch):
    import paho.mqtt.client as mqtt
    topico = f"viasegura/gs2026/teste/{uuid.uuid4().hex[:8]}/comando"   # tópico isolado: não mexe no nó real
    monkeypatch.setattr(m, "TOPICO_COMANDO", topico)
    recebido, pronto = [], threading.Event()
    sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    sub.on_connect = lambda c, *_: c.subscribe(topico, qos=1)
    sub.on_message = lambda c, u, msg: (recebido.append(json.loads(msg.payload)), pronto.set())
    sub.on_subscribe = lambda *_: threading.Timer(0, lambda: r.publicar([(0, m.comando("escola"))], dormir=lambda s: None)).start()
    sub.connect("test.mosquitto.org", 1883, keepalive=30)
    sub.loop_start()
    try:
        assert pronto.wait(15), "comando não chegou em 15 s"
    finally:
        sub.loop_stop()
        sub.disconnect()
    assert recebido[0]["modo"] == "escola" and m.validar_comando(recebido[0]) == []
