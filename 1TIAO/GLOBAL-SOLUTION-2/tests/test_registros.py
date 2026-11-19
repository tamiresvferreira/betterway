"""Registro manual de ocorrência pela câmera: rascunho, quadros com horário, envio com autoria e acionamentos."""
import sqlite3
from datetime import datetime

import numpy as np
import pytest

import ocorrencias as oc
import registros as rg
from autenticacao import Usuario
from perfis import SemPermissao

TRANSITO = Usuario("transito1", "Trânsito 1", "transito")
SAUDE = Usuario("saude1", "Saúde 1", "saude")
GESTAO = Usuario("gestao1", "Gestão 1", "gestao")
T0 = datetime(2026, 11, 18, 22, 10, 0)
T1 = datetime(2026, 11, 18, 22, 12, 30)


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    oc.migrar(c)
    rg.migrar(c)
    return c


@pytest.fixture
def video(tmp_path):
    import cv2
    f = tmp_path / "clipe.mp4"
    w = cv2.VideoWriter(str(f), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for i in range(30):                                    # 3 s; o brilho cresce a cada quadro
        w.write(np.full((48, 64, 3), i * 8, dtype=np.uint8))
    w.release()
    return f


def _novo(con, u=TRANSITO):
    return rg.iniciar(con, usuario=u, camera="CAM 02", local="Avenida do Imperador", cluster_id=7,
                      video_id="veo3_normal_01", agora=T0)


@pytest.mark.parametrize("u", [TRANSITO, SAUDE, GESTAO])
def test_qualquer_perfil_registra(con, u):
    i = _novo(con, u)
    r = rg.obter(con, i)
    assert (r["registrado_por"], r["registrado_em"], r["enviado_em"]) == (u.usuario, "2026-11-18T22:10:00", None)


def test_sem_perfil_nao_registra(con):
    with pytest.raises(SemPermissao):
        _novo(con, None)


def test_quadro_capturado_com_horario_e_autor(con, video, tmp_path):
    i = _novo(con)
    q = rg.capturar(con, i, usuario=TRANSITO, video=video, segundo=2.0, pasta=tmp_path / "q", agora=T1)
    assert q.arquivo.exists() and q.arquivo.suffix == ".png"
    assert (q.segundo, q.capturado_em, q.capturado_por) == (2.0, "2026-11-18T22:12:30", "transito1")
    assert "20261118T221230" in q.arquivo.name
    assert [x.id for x in rg.quadros(con, i)] == [q.id]


def test_momentos_diferentes_dao_quadros_diferentes(video):
    a, b = rg.quadro_do_video(video, 0.0), rg.quadro_do_video(video, 2.5)
    assert a is not None and b is not None and b.mean() > a.mean()
    assert rg.duracao_s(video) == pytest.approx(3.0, abs=0.2)


def test_remover_quadro_apaga_o_arquivo(con, video, tmp_path):
    i = _novo(con)
    q = rg.capturar(con, i, usuario=TRANSITO, video=video, segundo=1.0, pasta=tmp_path)
    rg.remover_quadro(con, q.id)
    assert rg.quadros(con, i) == [] and not q.arquivo.exists()


def test_envio_guarda_quem_enviou_e_quando(con):
    i = _novo(con)
    assert rg.enviar(con, i, usuario=GESTAO, situacao="veiculo_parado", descricao="  Carro quebrado na faixa ",
                     acionamentos=["transito", "policia"], agora=T1) is None
    r = rg.obter(con, i)
    assert (r["registrado_por"], r["enviado_por"], r["enviado_em"]) == ("transito1", "gestao1", "2026-11-18T22:12:30")
    assert (r["descricao"], r["acionamentos"]) == ("Carro quebrado na faixa", "transito,policia")
    assert [x["id"] for x in rg.enviados(con)] == [i]
    assert oc.listar(con) == []                        # sem ambulância, nada vai para a Saúde


def test_ambulancia_abre_ocorrencia_confirmada_para_a_saude(con):
    i = _novo(con)
    n = rg.enviar(con, i, usuario=TRANSITO, situacao="acidente", descricao="Atropelamento na faixa",
                  acionamentos=["ambulancia", "transito"], agora=T1)
    o = oc.obter(con, n)
    assert (o["estado"], o["tipo"], o["origem"], o["cluster_id"]) == ("confirmada", "registro_camera", "operador", 7)
    assert rg.obter(con, i)["ocorrencia_id"] == n
    assert oc.tempos(con, n)["confirmada"]["usuario"] == "transito1"
    assert oc.aplicar(con, n, "despachar", SAUDE) == "despachada"     # segue o fluxo normal da Saúde


@pytest.mark.parametrize("situacao, descricao, acion", [("", "algo", []), ("acidente", "   ", []),
                                                         ("acidente", "algo", ["bombeiro"])])
def test_envio_incompleto_e_recusado(con, situacao, descricao, acion):
    i = _novo(con)
    with pytest.raises(ValueError):
        rg.enviar(con, i, usuario=TRANSITO, situacao=situacao, descricao=descricao, acionamentos=acion)
    assert rg.obter(con, i)["enviado_em"] is None


def test_nao_envia_duas_vezes_nem_anexa_depois(con, video, tmp_path):
    i = _novo(con)
    rg.enviar(con, i, usuario=TRANSITO, situacao="outro", descricao="x", acionamentos=[])
    with pytest.raises(ValueError):
        rg.enviar(con, i, usuario=TRANSITO, situacao="outro", descricao="x", acionamentos=[])
    with pytest.raises(ValueError):
        rg.capturar(con, i, usuario=TRANSITO, video=video, segundo=1.0, pasta=tmp_path)


def test_ocorrencia_aponta_para_o_relatorio(con):
    i = _novo(con)
    n = rg.enviar(con, i, usuario=TRANSITO, situacao="acidente", descricao="x", acionamentos=["ambulancia"])
    assert rg.do_ocorrencia(con, n)["camera"] == "CAM 02" and rg.do_ocorrencia(con, 999) is None
