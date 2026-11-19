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
          "sala-de-controle": "sala", "cameras": "cameras", "sobre": "sobre", "equipe": "equipe", "perfil": "perfil"}


def _ir(at, pagina):
    at.session_state["ir_para"] = CHAVES[pagina]
    return at.run()


def test_sem_login_so_aparece_a_entrada_sem_textos_extras(banco):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["E-mail ou usuário", "Senha"]
    txt = _texto(at)
    assert "demonstração" not in txt and "Central de operação" not in txt and "Acesso por perfil" not in txt
    assert "To live, to move, <span>to drive, to be free.</span>" in txt and "Mais seguro para quem" not in txt


def test_senha_errada_nao_entra(banco):
    at = _entrar("transito1", "errada-errada")
    assert at.error and at.error[0].value == au.MSG_INCORRETO
    assert "Ninguém fica na faixa com os carros em verde" not in _texto(at)


def test_gestao_abre_na_visao_geral_e_o_painel_le_a_situacao(banco):
    at = _entrar("gestao1")
    assert not at.exception
    assert "Ninguém fica na faixa com os carros em verde" in _texto(at)
    at = _ir(at, "painel")
    assert not at.exception, at.exception
    assert "Leitura da situação" in _texto(at)


def test_visao_geral_um_cenario_por_vez_e_a_seta_avanca(banco, tmp_path, monkeypatch):
    import visao_geral as vg
    monkeypatch.setattr(vg, "PASTA_VIDEOS", tmp_path)          # sem vídeos: espaço reservado
    at = _entrar("gestao1")
    assert not at.exception, at.exception
    txt = _texto(at)
    assert "Ninguém fica na faixa com os carros em verde" in txt and "Faz o trânsito andar" not in txt
    assert "Vídeo do cenário em breve" in txt and "visao_geral_conflito.mp4" in txt
    assert "Leitura da situação" not in txt and "Tudo ligado junto" not in txt
    assert "to drive, to be free" in txt and "Mais seguro para quem" not in txt
    assert "dá olhos ao semáforo" in txt
    for titulo in ["Faz o trânsito andar", "Abre caminho para a ambulância", "Dá tempo a quem precisa atravessar",
                   "Ninguém fica na faixa com os carros em verde"]:
        at.button(key="vg_proximo").click().run()
        assert not at.exception, at.exception
        assert titulo in _texto(at)
    at.button(key="vg_ponto_2").click().run()
    assert "Abre caminho para a ambulância" in _texto(at)


def test_sobre_mostra_as_barras_do_sistema(banco):
    at = _ir(_entrar("gestao1"), "sobre")
    assert not at.exception, at.exception
    assert "Tudo ligado junto" in _texto(at)


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


@pytest.mark.parametrize("pagina", ["ocorrencias", "sala-de-controle", "cameras", "sobre"])
def test_gestao_so_le(banco, pagina):
    con = sqlite3.connect(banco)
    i = oc.abrir(con, origem="visao", tipo="suspeita_acidente", video_id="veo3_x_01", segundo=1.0)
    oc.aplicar(con, i, "confirmar", Usuario("transito1", "T", "transito"))
    con.close()
    at = _ir(_entrar("gestao1"), pagina)
    assert not at.exception, at.exception
    rotulos = {b.label for b in at.button}
    assert not rotulos & {"Confirmar", "Despachar ambulância (SIMULADA)", "Reportar ocorrência", "Normal"}


def test_abrir_uma_camera_registra_quem_abriu(banco):
    con = sqlite3.connect(banco)
    con.execute("CREATE TABLE clusters (cluster_id INTEGER, rank_urbano INTEGER, via_principal TEXT)")
    con.executemany("INSERT INTO clusters VALUES (?, ?, ?)", [(139, 26, "AVENIDA RANGEL PESTANA"),
                                                             (48, 1, "AVENIDA DO IMPERADOR")])
    con.commit()
    con.close()
    at = _ir(_entrar("saude1"), "cameras")
    assert not at.exception, at.exception
    assert at.segmented_control[0].options == ["CAM 01 · Largo da Concórdia", "CAM 02 · Avenida do Imperador"]
    at.segmented_control[0].set_value("CAM 01 · Largo da Concórdia").run()
    assert not at.exception, at.exception
    linhas = list(sqlite3.connect(banco).execute("SELECT usuario, camera FROM acessos_camera"))
    assert linhas == [("saude1", "CAM 01")]


def test_convite_pela_tela_e_login_com_codigo(banco):
    import totp
    con = sqlite3.connect(banco)
    token = au.convidar(con, "saude9", "saude", "Operador(a) Saúde 9", "s9@exemplo.org")
    con.close()
    at = AppTest.from_file(APP, default_timeout=90)
    at.query_params["convite"] = token
    at.run()
    assert not at.exception, at.exception
    segredo = at.session_state["segredo_convite"]
    at.text_input[0].input("senha-forte-9")
    at.text_input[1].input("senha-forte-9")
    at.text_input[2].input(totp.codigo(segredo))
    at.button[0].click().run()
    assert not at.exception, at.exception
    # login: senha, depois o código
    at = _entrar("saude9", "senha-forte-9")
    assert "Código do aplicativo" in [t.label for t in at.text_input]
    at.text_input[0].input(totp.codigo(segredo))
    at.button[0].click().run()
    assert "Ninguém fica na faixa com os carros em verde" in _texto(at)


def test_gestao_gera_convite_na_tela_equipe(banco):
    at = _ir(_entrar("gestao1"), "equipe")
    assert not at.exception, at.exception
    at.text_input(key="conv_nome").input("Bruno Alves")
    at.text_input(key="conv_email").input("bruno.alves@transito.exemplo.org")
    at.text_input(key="conv_cargo").input("Operador de tráfego")
    next(b for b in at.button if b.label == "Gerar convite").click().run()
    assert not at.exception, at.exception
    assert any("?convite=" in c.value for c in at.code)
    p = au.perfil(sqlite3.connect(banco), "bruno.alves")
    assert p.cargo == "Operador de tráfego" and p.convite_pendente


def test_meu_perfil_mostra_o_nome_e_salva_o_tratamento(banco):
    at = _ir(_entrar("saude1"), "perfil")
    assert not at.exception, at.exception
    campos = {t.label: t for t in at.text_input}
    campos["Como quer ser chamado(a) na plataforma"].input("Dani")
    next(b for b in at.button if b.label == "Salvar dados").click().run()
    assert not at.exception, at.exception
    assert au.perfil(sqlite3.connect(banco), "saude1").primeiro_nome == "Dani"
