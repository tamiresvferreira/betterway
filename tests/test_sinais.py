"""Sinal simulado do nó (plano B da demonstração): mesmo formato do ESP32, marcado como simulado."""
import pytest

import mensagens as m
import sinais as sn


@pytest.mark.parametrize("tipo", ["cartao_lido", "camera_pediu_tempo", "travessia_estendida"])
def test_sinal_simulado_e_um_evento_valido_e_marcado(tipo):
    e = sn.evento_simulado(tipo, 3)
    assert m.validar_evento(e) == []
    assert e["boot"] == "simulado" and e["detalhe"]["simulado"] is True and e["seq"] == 3


def test_tipo_inventado_e_recusado():
    with pytest.raises(ValueError):
        sn.evento_simulado("botao_pressionado", 1)          # o botão saiu: agora é cartão ou câmera
