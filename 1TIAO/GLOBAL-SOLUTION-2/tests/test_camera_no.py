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
    no.receber(m.TOPICO_EVENTO, json.dumps({"v": 1, "tipo": "botao_pressionado", "seq": 1, "boot": "x"}).encode())
    no.receber(m.TOPICO_EVENTO, b"lixo")
    assert no.estado["modo"] == "chuva" and no.estado_recebido_em is not None
    assert [e["tipo"] for e in no.eventos] == ["botao_pressionado"]
    assert no.publicar(m.comando("escola"))
    assert enviados[0][0] == m.TOPICO_COMANDO and json.loads(enviados[0][1])["modo"] == "escola"


def test_cenarios_da_sala_de_controle_sao_comandos_validos():
    for nome in nav.CENARIOS:
        assert m.validar_comando(nav.comando_cenario(nome)) == []
    assert nav.comando_cenario("alagamento")["alagamento"] is True
