"""Contrato MQTT do nó ESP32 (src/central/mensagens.py)."""
import math

import pytest

import mensagens as m


def test_topicos():
    assert m.TOPICO_COMANDO == "viasegura/gs2026/no/largo-concordia/comando"
    assert m.TOPICO_EVENTO.endswith("/evento") and m.TOPICO_ESTADO.endswith("/estado")


def test_comando_valido_tem_v_id_ts_sao_paulo():
    c = m.comando("chuva", alagamento=True)
    assert c["v"] == 1 and c["modo"] == "chuva" and c["alagamento"] is True
    assert c["ts"].endswith("-03:00") and len(c["id"]) >= 8
    assert m.validar_comando(c) == []


@pytest.mark.parametrize("modo, extra", [
    ("ambulancia", {"eta_s": -1}), ("ambulancia", {"eta_s": "25"}), ("ambulancia", {"eta_s": math.nan}),
    ("ambulancia", {"eta_s": True}), ("ambulancia", {}), ("voo", {}), ("chuva", {"eta_s": 10}),
    ("pedestre", {"faixa_ocupada": "sim"})])
def test_comando_invalido(modo, extra):
    with pytest.raises(m.ComandoInvalido):
        m.comando(modo, **extra)


def test_ambulancia_fim_dispensa_eta():
    assert m.comando("ambulancia", fim=True)["fim"] is True


def test_validar_comando_cru():
    assert m.validar_comando({"v": 1, "modo": "voo"})
    assert m.validar_comando({"v": 2, "id": "x", "modo": "normal", "ts": "t"})
    assert m.validar_comando([1, 2])


def test_validar_evento():
    ok = {"v": 1, "tipo": "cartao_lido", "seq": 3, "boot": "a1", "detalhe": {}}
    assert m.validar_evento(ok) == []
    assert m.validar_evento({**ok, "tipo": "x"})
    assert m.validar_evento({k: v for k, v in ok.items() if k != "seq"})
    assert m.validar_evento({**ok, "seq": -1}) and m.validar_evento({**ok, "v": 2})
    assert m.validar_evento({**ok, "boot": ""}) and m.validar_evento("texto")



def test_camera_pede_tempo_so_no_modo_pedestre():
    import mensagens as mm
    assert mm.validar_comando(mm.comando("pedestre", faixa_ocupada=True, estendida=True)) == []
    with pytest.raises(mm.ComandoInvalido):
        mm.comando("normal", estendida=True)
    with pytest.raises(mm.ComandoInvalido):
        mm.comando("pedestre", estendida="sim")
