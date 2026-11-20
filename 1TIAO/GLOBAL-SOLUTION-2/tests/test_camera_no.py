"""Câmera simulada (src/operador/camera.py) e estado do nó ao vivo (src/operador/no_ao_vivo.py)."""
import json

import camera as cam
import mensagens as m
import no_ao_vivo as nav


def _clipes(*nomes):
    return [cam.Clipe(n, cam.categoria(n), None, [], True) for n in nomes]


def test_clipe_segue_o_modo_do_no():
    cs = _clipes("normal_01", "cadeirante_01", "bengala_01", "chuva_01", "ambulancia_01", "suspeita_acidente_01")
    assert cam.clipe_para_modo("ambulancia", cs, 0).nome == "ambulancia_01"
    assert cam.clipe_para_modo("chuva", cs, 0).nome == "chuva_01"
    assert {cam.clipe_para_modo("pedestre", cs, i).nome for i in range(4)} == {"cadeirante_01", "bengala_01"}


def test_sem_clipe_do_modo_usa_qualquer_um_e_lista_vazia_da_none():
    cs = _clipes("normal_01")
    assert cam.clipe_para_modo("escola", cs, 0).nome == "normal_01"
    assert cam.clipe_para_modo("normal", [], 0) is None
    assert cam.clipe_para_modo(None, cs, 0).nome == "normal_01"


def test_player_rotula_sintetico_e_leva_os_eventos():
    c = cam.Clipe("suspeita_acidente_01", "suspeita_acidente", None,
                  [{"tipo": "suspeita_acidente", "segundo": 4.2}], True)
    html = cam.html_player(c, "normal", video_b64="AAAA")
    assert "clipe sintético (Veo 3)" in html and "Suspeita de acidente" in html and "4.2" in html
    real = cam.Clipe("cdmx", "pedestre", None, [], False)
    assert "vídeo real" in cam.html_player(real, "pedestre", video_b64="AAAA")


def test_no_ao_vivo_guarda_o_ultimo_estado_e_os_eventos():
    enviados = []
    no = nav.NoAoVivo(publicar_bruto=lambda t, p: enviados.append((t, p)) or True)
    no.receber(m.TOPICO_ESTADO, json.dumps({"v": 1, "modo": "chuva", "fase": "verde_veiculos"}).encode())
    no.receber(m.TOPICO_EVENTO, json.dumps({"v": 1, "tipo": "cartao_lido", "seq": 1, "boot": "x"}).encode())
    no.receber(m.TOPICO_EVENTO, b"lixo")
    assert no.estado["modo"] == "chuva" and no.estado_recebido_em is not None
    assert [e["tipo"] for e in no.eventos] == ["cartao_lido"]
    assert no.publicar(m.comando("escola"))
    assert enviados[0][0] == m.TOPICO_COMANDO and json.loads(enviados[0][1])["modo"] == "escola"


def test_cenarios_da_sala_de_controle_sao_comandos_validos():
    for nome in nav.CENARIOS:
        assert m.validar_comando(nav.comando_cenario(nome)) == []
    assert nav.comando_cenario("alagamento")["alagamento"] is True


# ---------------------------------------------------------------- rede de câmeras
PONTOS = [{"cluster_id": 48, "rank_urbano": 1, "via_principal": "AVENIDA DO IMPERADOR"},
          {"cluster_id": 139, "rank_urbano": 26, "via_principal": "AVENIDA RANGEL PESTANA"},
          {"cluster_id": 267, "rank_urbano": 2, "via_principal": "AVENIDA BRAZ LEME"},
          {"cluster_id": 225, "rank_urbano": 3, "via_principal": "AVENIDA DO ESTADO"}]


def test_rede_comeca_pelo_piloto_e_marca_as_simuladas():
    cs = _clipes("normal_01", "cadeirante_01")
    rede = cam.rede_de_cameras(PONTOS, cs, piloto=139, n=4)
    assert [c.id for c in rede] == ["CAM 01", "CAM 02", "CAM 03", "CAM 04"]
    assert rede[0].cluster_id == 139 and rede[0].instalada and rede[0].local == "Largo da Concórdia"
    assert all(not c.instalada for c in rede[1:])
    assert [c.cluster_id for c in rede[1:]] == [48, 267, 225]           # pela ordem do ranking
    assert rede[1].local == "Avenida do Imperador"
    assert {c.clipe.nome for c in rede} == {"normal_01", "cadeirante_01"}


def test_rede_sem_clipes_nao_quebra():
    assert all(c.clipe is None for c in cam.rede_de_cameras(PONTOS, [], piloto=139, n=3))


def test_quem_abre_uma_camera_fica_registrado():
    import sqlite3
    con = sqlite3.connect(":memory:")
    cam.migrar(con)
    cam.registrar_visualizacao(con, "saude1", "CAM 01")
    cam.registrar_visualizacao(con, "gestao1", "CAM 03")
    linhas = list(con.execute("SELECT usuario, camera FROM acessos_camera ORDER BY id"))
    assert linhas == [("saude1", "CAM 01"), ("gestao1", "CAM 03")]


def test_player_aceita_url_em_vez_de_embutir_o_video():
    c = cam.Clipe("cdmx", "pedestre", None, [], False)
    h = cam.html_player(c, "normal", video_url="app/static/cameras/cdmx.mp4")
    assert 'src="app/static/cameras/cdmx.mp4"' in h and "base64" not in h


def test_camera_do_piloto_toca_o_clipe_escolhido_e_as_outras_fazem_rodizio():
    cs = _clipes("cadeirante_01", "cadeirante_02", "normal_01")
    rede = cam.rede_de_cameras(PONTOS, cs, piloto=139, n=4, clipe_piloto="cadeirante_02")
    assert rede[0].clipe.nome == "cadeirante_02"
    assert [c.clipe.nome for c in rede[1:]] == ["cadeirante_01", "normal_01", "cadeirante_01"]
