"""Plataforma BetterWay (src/operador/app.py) com AppTest: login de verdade, navegação por perfil e fluxo da ocorrência."""
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
    at = AppTest.from_file(APP, default_timeout=90).run()
    at.text_input[0].input(usuario)
    at.text_input[1].input(senha)
    at.button[0].click().run()
    return at


def _texto(at):
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption] + [t.value for t in at.title])


CHAVES = {"painel": "painel", "camera": "camera", "confirmadas": "confirmadas", "ocorrencias": "ocorrencias",
          "sala-de-controle": "sala", "estudos": "estudos"}


def _ir(at, pagina):
    at.session_state["ir_para"] = CHAVES[pagina]
    return at.run()


def test_sem_login_so_aparece_a_entrada_sem_textos_extras(banco):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["Usuário", "Senha"]
    txt = _texto(at)
    assert "demonstração" not in txt and "Central de operação" not in txt and "Acesso por perfil" not in txt


def test_senha_errada_nao_entra(banco):
    at = _entrar("transito1", "errada-errada")
    assert at.error and at.error[0].value == au.MSG_INCORRETO
    assert "Mais seguro para quem atravessa" not in _texto(at)


def test_gestao_abre_na_visao_geral_e_o_painel_le_a_situacao(banco):
    at = _entrar("gestao1")
    assert not at.exception
    assert "O que a plataforma faz" in _texto(at)
    at = _ir(at, "painel")
    assert not at.exception, at.exception
    assert "Leitura da situação" in _texto(at)


def test_transito_confirma_e_saude_ve(banco):
    con = sqlite3.connect(banco)
    i = oc.abrir(con, origem="visao", tipo="suspeita_acidente", video_id="veo3_suspeita_acidente_01", segundo=4.0)
    con.close()
    at = _ir(_entrar("transito1"), "camera")
    assert not at.exception, at.exception
    next(b for b in at.button if b.label == "Confirmar").click().run()
    assert oc.obter(sqlite3.connect(banco), i)["estado"] == "confirmada"
    at = _ir(_entrar("saude1"), "confirmadas")
    assert not at.exception
    assert any(b.label == "Despachar ambulância (SIMULADA)" for b in at.button)
    assert not any(b.label == "Confirmar" for b in at.button)


@pytest.mark.parametrize("pagina", ["ocorrencias", "sala-de-controle", "estudos"])
def test_gestao_so_le(banco, pagina):
    con = sqlite3.connect(banco)
    i = oc.abrir(con, origem="visao", tipo="suspeita_acidente", video_id="veo3_x_01", segundo=1.0)
    oc.aplicar(con, i, "confirmar", Usuario("transito1", "T", "transito"))
    con.close()
    at = _ir(_entrar("gestao1"), pagina)
    assert not at.exception, at.exception
    rotulos = {b.label for b in at.button}
    assert not rotulos & {"Confirmar", "Despachar ambulância (SIMULADA)", "Reportar ocorrência", "Normal"}
