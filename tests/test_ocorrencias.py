"""Ocorrências (src/operador/ocorrencias.py) e despacho da ambulância SIMULADA (src/operador/despacho.py)."""
import sqlite3
from datetime import datetime, timedelta

import pytest

import despacho as dp
import mensagens as m
import ocorrencias as oc
from autenticacao import Usuario
from perfis import SemPermissao

T0 = datetime(2026, 11, 18, 9, 0, tzinfo=m.FUSO)
TRANSITO = Usuario("transito1", "Operador(a) Trânsito 1", "transito")
SAUDE = Usuario("saude1", "Operador(a) Saúde 1", "saude")
GESTAO = Usuario("gestao1", "Gestão 1", "gestao")


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    oc.migrar(c)
    return c


def _da_visao(con, segundo=4.0):
    return oc.abrir(con, origem="visao", tipo="suspeita_acidente", video_id="veo3_suspeita_acidente_01",
                    segundo=segundo, agora=T0)


def test_fluxo_completo_grava_quem_e_quando(con):
    i = _da_visao(con)
    assert oc.aplicar(con, i, "confirmar", TRANSITO, agora=T0 + timedelta(seconds=40)) == "confirmada"
    assert oc.aplicar(con, i, "despachar", SAUDE, agora=T0 + timedelta(seconds=70)) == "despachada"
    assert oc.aplicar(con, i, "encerrar", SAUDE, agora=T0 + timedelta(minutes=10)) == "encerrada"
    t = oc.tempos(con, i)
    assert list(t) == ["pendente", "confirmada", "despachada", "encerrada"]
    assert t["confirmada"]["usuario"] == "transito1" and t["despachada"]["usuario"] == "saude1"
    assert t["pendente"]["usuario"] == "visao"


def test_perfil_errado_e_recusado_na_funcao(con):
    i = _da_visao(con)
    with pytest.raises(SemPermissao):
        oc.aplicar(con, i, "confirmar", SAUDE)
    with pytest.raises(SemPermissao):
        oc.aplicar(con, i, "confirmar", GESTAO)
    assert oc.obter(con, i)["estado"] == "pendente"


def test_ordem_errada_e_recusada(con):
    i = _da_visao(con)
    with pytest.raises(oc.TransicaoInvalida):
        oc.aplicar(con, i, "despachar", SAUDE)
    oc.aplicar(con, i, "descartar", TRANSITO, motivo="pessoa se levantou")
    with pytest.raises(oc.TransicaoInvalida):
        oc.aplicar(con, i, "confirmar", TRANSITO)


def test_descartar_exige_motivo(con):
    i = _da_visao(con)
    with pytest.raises(ValueError):
        oc.aplicar(con, i, "descartar", TRANSITO, motivo="  ")
    oc.aplicar(con, i, "descartar", TRANSITO, motivo="falso alarme")
    assert oc.tempos(con, i)["descartada"]["motivo"] == "falso alarme"


def test_visao_nao_abre_a_mesma_ocorrencia_duas_vezes(con):
    assert _da_visao(con) == _da_visao(con)
    assert len(oc.listar(con)) == 1


def test_reportar_so_pelo_transito(con):
    i = oc.abrir(con, origem="operador", tipo="ocorrencia_reportada", usuario=TRANSITO, agora=T0)
    assert oc.obter(con, i)["origem"] == "operador"
    with pytest.raises(SemPermissao):
        oc.abrir(con, origem="operador", tipo="ocorrencia_reportada", usuario=SAUDE)
    with pytest.raises(SemPermissao):
        oc.abrir(con, origem="operador", tipo="ocorrencia_reportada", usuario=None)


def test_listar_filtra_por_estado(con):
    a, b = _da_visao(con, 1.0), _da_visao(con, 2.0)
    oc.aplicar(con, a, "confirmar", TRANSITO)
    assert [o["id"] for o in oc.listar(con, ["confirmada"])] == [a]
    assert [o["id"] for o in oc.listar(con, ["pendente"])] == [b]


# ---------------------------------------------------------------- despacho
def test_comando_de_despacho_conta_o_eta_e_termina_em_fim():
    cmds = [dp.comando_despacho(t) for t in range(0, 60)]
    etas = [c["eta_s"] for c in cmds if c and "eta_s" in c]
    assert etas[0] == 54 and etas == sorted(etas, reverse=True)
    assert any(c and c.get("fim") for c in cmds)
    assert all(m.validar_comando(c) == [] for c in cmds if c)
    assert dp.comando_despacho(200) is None


def test_despachante_envia_a_cada_10_s_e_o_fim_uma_vez():
    enviados = []
    d = dp.Despachante(lambda c: enviados.append(c) or True)
    for t in range(0, 80):
        d.passo([(7, float(t))])
    etas = [c for c in enviados if "eta_s" in c]
    fins = [c for c in enviados if c.get("fim")]
    assert 5 <= len(etas) <= 7 and len(fins) == 1


def test_despachante_nao_reenvia_despacho_antigo_ao_reiniciar():
    enviados = []
    dp.Despachante(lambda c: enviados.append(c) or True).passo([(7, 600.0)])
    assert enviados == []


def test_despachadas_recentes_vem_do_historico(con):
    i = _da_visao(con)
    oc.aplicar(con, i, "confirmar", TRANSITO, agora=T0)
    oc.aplicar(con, i, "despachar", SAUDE, agora=T0 + timedelta(seconds=10))
    assert dp.despachadas_recentes(con, T0 + timedelta(seconds=30)) == [(i, 20.0)]
    assert dp.despachadas_recentes(con, T0 + timedelta(hours=1)) == []
