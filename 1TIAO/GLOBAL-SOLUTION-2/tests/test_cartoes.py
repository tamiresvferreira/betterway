"""Leituras de cartão (e pedidos da câmera): registro sem dado pessoal e tempo extra igual ao do nó."""
import sqlite3
from datetime import datetime

import pytest

import cartoes as ct


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    ct.migrar(c)
    return c


def test_cartao_registra_tipo_e_tempo_extra_do_no(con):
    r = ct.registrar(con, origem="cartao", tipo="idoso", agora=datetime(2026, 11, 19, 18, 0))
    assert (r["tempo_s"], r["extra_s"]) == (12.5, 4.2)          # 10 m ÷ 0,8 m/s; 12,5 − 8,3
    linha = ct.recentes(con)[0]
    assert set(linha) == {"id", "timestamp", "origem", "tipo", "faixa", "tempo_s", "extra_s", "simulado"}  # sem número


def test_camera_nao_tem_tipo_de_cartao(con):
    assert ct.registrar(con, origem="camera", tipo="idoso")["tipo"] is None


@pytest.mark.parametrize("origem, tipo", [("cartao", None), ("cartao", "estudante"), ("botao", "idoso")])
def test_entrada_invalida(con, origem, tipo):
    with pytest.raises(ValueError):
        ct.registrar(con, origem=origem, tipo=tipo)


def test_sms_sem_travessao_e_com_distancia():
    m = ct.mensagem_sms("Avenida Rangel Pestana")
    assert "1 km" in m and "Avenida Rangel Pestana" in m and "—" not in m
