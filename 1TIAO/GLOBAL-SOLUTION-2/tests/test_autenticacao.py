"""Autenticação e permissões da interface do operador (src/operador/autenticacao.py, perfis.py)."""
import sqlite3
from datetime import datetime, timedelta

import pytest

import autenticacao as au
import perfis as pf

T0 = datetime(2026, 11, 18, 9, 0)


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    au.migrar(c)
    au.criar_usuario(c, "transito1", "transito", "Operador(a) Trânsito 1", "senha-forte-1")
    return c


def test_senha_certa_entra_e_devolve_perfil(con):
    r = au.autenticar(con, "transito1", "senha-forte-1", agora=T0)
    assert r.ok and r.usuario.perfil == "transito" and r.usuario.nome == "Operador(a) Trânsito 1"


def test_senha_errada_e_usuario_inexistente_dao_a_mesma_mensagem(con):
    errada = au.autenticar(con, "transito1", "outra-senha", agora=T0)
    inexistente = au.autenticar(con, "ninguem", "outra-senha", agora=T0)
    assert not errada.ok and not inexistente.ok
    assert errada.mensagem == inexistente.mensagem == au.MSG_INCORRETO


def test_cinco_erros_bloqueiam_e_o_bloqueio_expira(con):
    for i in range(au.MAX_TENTATIVAS):
        au.autenticar(con, "transito1", "errada!!", agora=T0 + timedelta(seconds=i))
    bloqueado = au.autenticar(con, "transito1", "senha-forte-1", agora=T0 + timedelta(minutes=1))
    assert not bloqueado.ok and bloqueado.mensagem == au.MSG_BLOQUEADO
    depois = au.autenticar(con, "transito1", "senha-forte-1", agora=T0 + timedelta(minutes=au.BLOQUEIO_MIN, seconds=10))
    assert depois.ok


def test_acerto_zera_as_tentativas(con):
    for i in range(au.MAX_TENTATIVAS - 1):
        au.autenticar(con, "transito1", "errada!!", agora=T0)
    assert au.autenticar(con, "transito1", "senha-forte-1", agora=T0).ok
    au.autenticar(con, "transito1", "errada!!", agora=T0)
    assert au.autenticar(con, "transito1", "senha-forte-1", agora=T0).ok


def test_mesma_senha_em_dois_usuarios_gera_hashes_diferentes(con):
    au.criar_usuario(con, "transito2", "transito", "Operador(a) Trânsito 2", "senha-forte-1")
    h = [r[0] for r in con.execute("SELECT hash FROM usuarios WHERE usuario LIKE 'transito%'")]
    assert len(set(h)) == 2 and "senha-forte-1" not in "".join(h)


def test_senha_curta_perfil_invalido_e_usuario_repetido_sao_recusados(con):
    with pytest.raises(ValueError):
        au.criar_usuario(con, "x", "transito", "X", "curta")
    with pytest.raises(ValueError):
        au.criar_usuario(con, "y", "admin", "Y", "senha-forte-1")
    with pytest.raises(ValueError):
        au.criar_usuario(con, "transito1", "saude", "Z", "senha-forte-1")


def test_usuario_inativo_nao_entra(con):
    con.execute("UPDATE usuarios SET ativo = 0 WHERE usuario = 'transito1'")
    assert not au.autenticar(con, "transito1", "senha-forte-1", agora=T0).ok


def test_acessos_registram_entrada_e_falha_sem_senha(con):
    au.autenticar(con, "transito1", "senha-forte-1", agora=T0)
    au.autenticar(con, "transito1", "errada!!", agora=T0)
    linhas = list(con.execute("SELECT usuario, evento FROM acessos ORDER BY id"))
    assert linhas == [("transito1", "entrada"), ("transito1", "falha")]
    assert "errada" not in str(list(con.execute("SELECT * FROM acessos")))


def test_sessao_expira_apos_30_min_sem_uso():
    assert au.sessao_valida(T0, T0 + timedelta(minutes=29))
    assert not au.sessao_valida(T0, T0 + timedelta(minutes=au.SESSAO_MIN, seconds=1))
    assert not au.sessao_valida(None, T0)


def test_permissoes_por_perfil():
    assert pf.pode("transito", "confirmar") and pf.pode("transito", "reportar") and pf.pode("transito", "cenario")
    assert pf.pode("saude", "despachar") and pf.pode("saude", "encerrar")
    assert not pf.pode("saude", "confirmar") and not pf.pode("transito", "despachar")
    assert not any(pf.pode("gestao", a) for a in pf.ACOES)
    assert not pf.pode("intruso", "confirmar") and not pf.pode(None, "confirmar")
