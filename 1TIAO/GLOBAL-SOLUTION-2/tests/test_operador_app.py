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
          "sala-de-controle": "sala", "cameras": "cameras", "sobre": "sobre", "equipe": "equipe", "perfil": "perfil",
          "demonstracoes": "demos"}


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
                   "A câmera percebe quem esqueceu o cartão", "Ninguém fica na faixa com os carros em verde"]:
        at.button(key="vg_proximo").click().run()
        assert not at.exception, at.exception
        assert titulo in _texto(at)
    at.button(key="vg_ponto_2").click().run()
    assert "Abre caminho para a ambulância" in _texto(at)
    at.button(key="vg_anterior").click().run()
    assert "Faz o trânsito andar" in _texto(at)


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


def _clusters(banco):
    con = sqlite3.connect(banco)
    con.execute("CREATE TABLE clusters (cluster_id INTEGER, rank_urbano INTEGER, via_principal TEXT)")
    con.executemany("INSERT INTO clusters VALUES (?, ?, ?)", [(139, 26, "AVENIDA RANGEL PESTANA"),
                                                             (48, 1, "AVENIDA DO IMPERADOR")])
    con.commit()
    con.close()


def test_clicar_na_camera_abre_e_registra_quem_abriu(banco):
    _clusters(banco)
    at = _ir(_entrar("saude1"), "cameras")
    assert not at.exception, at.exception
    assert not at.segmented_control                                   # o seletor saiu: o cartão é clicável
    assert {b.key for b in at.button} >= {"abrir_CAM_01", "abrir_CAM_02"}
    at.button(key="abrir_CAM_01").click().run()
    assert not at.exception, at.exception
    assert "CAM 01 · Largo da Concórdia" in _texto(at)
    linhas = list(sqlite3.connect(banco).execute("SELECT usuario, camera FROM acessos_camera"))
    assert linhas == [("saude1", "CAM 01")]
    at.button(key="cam_voltar").click().run()
    assert "abrir_CAM_02" in {b.key for b in at.button}


def test_saude_ve_relatorio_de_camera_com_video(banco):
    import registros as rg
    con = sqlite3.connect(banco)
    rg.migrar(con)
    i = rg.iniciar(con, usuario=Usuario("transito1", "T", "transito"), camera="CAM 03", local="Avenida Braz Leme",
                   cluster_id=5, video_id="veo3_normal_01")
    rg.enviar(con, i, usuario=Usuario("transito1", "T", "transito"), situacao="acidente", descricao="x",
              acionamentos=["ambulancia"])
    con.close()
    at = _ir(_entrar("saude1"), "confirmadas")
    assert not at.exception, at.exception
    assert "Avenida Braz Leme" in _texto(at) and "CAM 03" in _texto(at)


def test_rascunho_sobrevive_a_sair_da_camera_e_voltar(banco):
    _clusters(banco)
    at = _ir(_entrar("saude1"), "cameras")
    at.button(key="abrir_CAM_01").click().run()
    at.button(key="reg_comecar").click().run()
    at.selectbox[0].set_value("pessoa_ajuda")
    at.text_area[0].input("Idosa caída na calçada.")
    [amb] = [cb for cb in at.checkbox if "Ambulância" in cb.label]
    amb.check()
    at.run()
    at.button(key="cam_voltar").click().run()
    at.button(key="abrir_CAM_01").click().run()
    assert not at.exception, at.exception
    assert at.selectbox[0].value == "pessoa_ajuda" and at.text_area[0].value == "Idosa caída na calçada."
    assert [cb.value for cb in at.checkbox if "Ambulância" in cb.label] == [True]


def test_relatorio_pela_camera_com_ambulancia_vai_para_a_saude(banco):
    _clusters(banco)
    at = _ir(_entrar("transito1"), "cameras")
    at.button(key="abrir_CAM_02").click().run()
    at.button(key="reg_comecar").click().run()
    assert not at.exception, at.exception
    at.selectbox[0].set_value("acidente")
    at.text_area[0].input("Moto caiu na faixa; pessoa consciente.")
    for cb in at.checkbox:
        if "Ambulância" in cb.label or "Polícia" in cb.label:
            cb.check()
    at.run()
    [enviar] = [b for b in at.button if (b.key or "").startswith("reg_enviar_")]
    enviar.click().run()
    assert not at.exception, at.exception
    assert any("enviado" in s.value and "Atendimentos" in s.value for s in at.success)
    con = sqlite3.connect(banco)
    r = con.execute("SELECT camera, registrado_por, enviado_por, enviado_em, acionamentos, ocorrencia_id "
                    "FROM registros").fetchone()
    assert r[:3] == ("CAM 02", "transito1", "transito1") and r[3] and r[4] == "ambulancia,policia" and r[5]
    con.close()
    saude = _ir(_entrar("saude1"), "confirmadas")
    assert "Avenida do Imperador" in _texto(saude) and "relatório Nº" in _texto(saude)


def test_sala_registra_cartao_e_camera_sem_validacao_manual(banco):
    at = _ir(_entrar("saude1"), "sala-de-controle")
    assert not at.exception, at.exception
    at.selectbox(key="sim_tipo").set_value("cartao_lido")
    at.button(key="sim_enviar").click().run()
    at.selectbox(key="sim_tipo").set_value("camera_pediu_tempo")
    at.button(key="sim_enviar").click().run()
    assert not at.exception, at.exception
    txt = _texto(at)
    assert "Cartão lido: pedido de mais tempo" in txt and "A câmera viu quem precisa de mais tempo" in txt
    assert "Verde do pedestre estendido" in txt and "simulado" in txt
    assert not [b for b in at.button if (b.key or "").startswith(("sconf_", "scont_"))]   # ninguém precisa liberar


def test_transito_ve_o_modo_camera_pede_tempo(banco):
    at = _ir(_entrar("transito1"), "sala-de-controle")
    assert not at.exception, at.exception
    assert "cen_camera_tempo" in {b.key for b in at.button}


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


def test_botao_de_tema_troca_claro_e_escuro_e_mantem_entre_paginas(banco):
    at = _entrar("gestao1")
    antes = at.session_state["tema"]
    at.button(key="tema_trocar").click().run()
    assert not at.exception, at.exception
    depois = at.session_state["tema"]
    assert {antes, depois} == {"light", "dark"}
    at = _ir(at, "sobre")
    assert at.session_state["tema"] == depois
    assert any("--bw-fundo:" + ("#EEEFEC" if depois == "light" else "#181818") in m.value for m in at.markdown)


def test_sobre_mostra_onde_a_betterway_funciona(banco):
    at = _ir(_entrar("gestao1"), "sobre")
    assert not at.exception, at.exception
    txt = _texto(at)
    assert "Onde a BetterWay funciona" in txt and "Faixa no meio da quadra" in txt and "Frente de escola" in txt


def test_central_de_demonstracoes_cartao_e_celular(banco):
    at = _ir(_entrar("saude1"), "demonstracoes")
    assert not at.exception, at.exception
    at.button(key="demo_ler").click().run()
    assert not at.exception, at.exception
    assert "Tempo extra concedido" in _texto(at) and "Bilhete Único Idoso" in _texto(at)
    linha = sqlite3.connect(banco).execute("SELECT origem, tipo, simulado FROM leituras_cartao").fetchone()
    assert linha == ("cartao", "idoso", 1)
    at.button(key="demo_sms_btn").click().run()
    assert "Alerta BetterWay: ambulância a 1 km" in _texto(at)
