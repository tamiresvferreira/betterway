"""Interface do operador (src/operador/app.py) com AppTest: login de verdade, perfis e fluxo da ocorrência."""
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import autenticacao as au  # noqa: E402
import ocorrencias as oc  # noqa: E402
from autenticacao import Usuario  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "src" / "operador" / "app.py")
SENHA = "senha-de-teste-1"


@pytest.fixture
def banco(tmp_path, monkeypatch):
    db = tmp_path / "op.db"
    con = sqlite3.connect(db)
    au.migrar(con)
    oc.migrar(con)
    for u, p in [("transito1", "transito"), ("saude1", "saude"), ("gestao1", "gestao")]:
        au.criar_usuario(con, u, p, f"Operador(a) {p} 1", SENHA)
    con.close()
    monkeypatch.setenv("VIA_SEGURA_DB", str(db))
    monkeypatch.setenv("BETTERWAY_SEM_MQTT", "1")
    monkeypatch.setenv("BETTERWAY_SEM_CLIPES", "1")
    return db


def _entrar(usuario, senha=SENHA):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input[0].input(usuario)
    at.text_input[1].input(senha)
    at.button[0].click().run()
    return at


def _textos(at):
    return " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)


def test_sem_login_so_aparece_a_tela_de_entrada_com_o_aviso(banco):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["Usuário", "Senha"]
    assert len(at.sidebar.radio) == 0
    assert "sem integração com CET ou SAMU" in _textos(at)


def test_senha_errada_nao_entra(banco):
    at = _entrar("transito1", "errada-errada")
    assert at.error and at.error[0].value == au.MSG_INCORRETO
    assert len(at.sidebar.radio) == 0


def test_transito_confirma_e_saude_ve(banco):
    con = sqlite3.connect(banco)
    i = oc.abrir(con, origem="visao", tipo="suspeita_acidente", video_id="veo3_suspeita_acidente_01", segundo=4.0)
    con.close()
    at = _entrar("transito1")
    assert not at.exception and at.sidebar.radio[0].options == ["Câmera e ocorrências", "Sala de controle"]
    assert "sem integração com CET ou SAMU" in _textos(at)
    next(b for b in at.button if b.label == "Confirmar").click().run()
    assert oc.obter(sqlite3.connect(banco), i)["estado"] == "confirmada"

    at = _entrar("saude1")
    assert not at.exception
    assert any(b.label == "Despachar ambulância (SIMULADA)" for b in at.button)
    assert not any(b.label == "Confirmar" for b in at.button)


def test_gestao_so_le(banco):
    con = sqlite3.connect(banco)
    i = oc.abrir(con, origem="visao", tipo="suspeita_acidente", video_id="veo3_x_01", segundo=1.0)
    oc.aplicar(con, i, "confirmar", Usuario("transito1", "T", "transito"))
    con.close()
    at = _entrar("gestao1")
    assert not at.exception and "Painel" in at.sidebar.radio[0].options
    for tela in at.sidebar.radio[0].options:
        if tela == "Painel":
            continue
        at.sidebar.radio[0].set_value(tela).run()
        assert not at.exception, tela
        rotulos = {b.label for b in at.button}
        assert not rotulos & {"Confirmar", "Despachar ambulância (SIMULADA)", "Reportar ocorrência", "Normal"}, tela
        assert "sem integração com CET ou SAMU" in _textos(at)


def test_sair_volta_para_a_entrada(banco):
    at = _entrar("saude1")
    next(b for b in at.sidebar.button if b.label == "Sair").click().run()
    assert [t.label for t in at.text_input] == ["Usuário", "Senha"]
