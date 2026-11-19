"""Validação dos sinais do nó (Sala de controle): Trânsito e Saúde confirmam ou contestam, com quem, área e hora."""
import sqlite3
from datetime import datetime

import pytest

import mensagens as m
import sinais as sn
from autenticacao import Usuario
from perfis import SemPermissao

TRANSITO = Usuario("transito1", "Trânsito 1", "transito")
SAUDE = Usuario("saude1", "Saúde 1", "saude")
GESTAO = Usuario("gestao1", "Gestão 1", "gestao")
T0 = datetime(2026, 11, 19, 10, 0, 0)
EV = {"v": 1, "tipo": "botao_pressionado", "seq": 7, "boot": "b1", "recebido_em": "2026-11-19T09:59:50-03:00"}


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    sn.migrar(c)
    return c


@pytest.mark.parametrize("u, area", [(TRANSITO, "Trânsito"), (SAUDE, "Saúde")])
def test_transito_e_saude_validam_com_quem_e_area(con, u, area):
    sn.validar(con, EV, usuario=u, decisao="confirmado", agora=T0)
    v = sn.validacoes(con)[("b1", 7)]
    assert (v["decisao"], v["usuario"], v["area"], v["timestamp"]) == ("confirmado", u.usuario, area,
                                                                       "2026-11-19T10:00:00")
    assert v["tipo"] == "botao_pressionado"


def test_gestao_so_acompanha(con):
    with pytest.raises(SemPermissao):
        sn.validar(con, EV, usuario=GESTAO, decisao="confirmado")


def test_contestar_exige_motivo(con):
    with pytest.raises(ValueError):
        sn.validar(con, EV, usuario=SAUDE, decisao="contestado", nota="  ")
    sn.validar(con, EV, usuario=SAUDE, decisao="contestado", nota="Ninguém na faixa na câmera")
    assert sn.validacoes(con)[("b1", 7)]["nota"] == "Ninguém na faixa na câmera"


def test_cada_sinal_e_validado_uma_vez(con):
    sn.validar(con, EV, usuario=TRANSITO, decisao="confirmado")
    with pytest.raises(ValueError):
        sn.validar(con, EV, usuario=SAUDE, decisao="confirmado")
    assert sn.validacoes(con)[("b1", 7)]["usuario"] == "transito1"


def test_decisao_desconhecida(con):
    with pytest.raises(ValueError):
        sn.validar(con, EV, usuario=TRANSITO, decisao="talvez")


def test_sinal_simulado_e_um_evento_valido_e_marcado():
    e = sn.evento_simulado("travessia_estendida", 3)
    assert m.validar_evento(e) == []
    assert e["boot"] == "simulado" and e["detalhe"]["simulado"] is True and e["seq"] == 3
    with pytest.raises(ValueError):
        sn.evento_simulado("inventado", 1)
