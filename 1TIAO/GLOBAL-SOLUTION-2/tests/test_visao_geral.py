"""Visão geral em quatro cenários: ordem, navegação pela seta e procura do vídeo de cada cenário."""
from pathlib import Path

import pytest

import visao_geral as vg

EVID_A = Path(__file__).resolve().parents[1] / "docs" / "evidencias" / "estudo_a"


def test_cinco_cenarios_na_ordem_dos_pilares():
    assert [c.id for c in vg.CENARIOS] == ["conflito", "transito", "ambulancia", "pedestre", "andador"]
    assert [c.verbo for c in vg.CENARIOS] == ["to live", "to move", "to move", "to be free", "to be free"]


def test_cada_cenario_tem_a_simulacao_exportada():
    for c in vg.CENARIOS:
        assert (EVID_A / f"cena_{c.cena}.json").exists(), c.cena


def test_textos_sem_travessao():
    for c in vg.CENARIOS:
        assert "—" not in c.titulo + c.texto


@pytest.mark.parametrize("i, esperado", [(0, 1), (1, 2), (3, 4), (4, 0)])
def test_seta_avanca_e_volta_ao_primeiro(i, esperado):
    assert vg.proximo(i) == esperado


def test_video_ausente_devolve_none(tmp_path):
    assert vg.video_do_cenario(vg.CENARIOS[2], tmp_path) is None
    assert vg.video_do_cenario(vg.CENARIOS[2], tmp_path / "nao_existe") is None


def test_video_presente_devolve_o_caminho(tmp_path):
    f = tmp_path / "visao_geral_ambulancia.mp4"
    f.write_bytes(b"\x00")
    assert vg.video_do_cenario(vg.CENARIOS[2], tmp_path) == f
    assert vg.CENARIOS[2].arquivo_video == "visao_geral_ambulancia.mp4"


@pytest.mark.parametrize("i, esperado", [(0, 4), (1, 0), (4, 3)])
def test_seta_de_voltar_vai_ao_anterior_e_do_primeiro_ao_ultimo(i, esperado):
    assert vg.anterior(i) == esperado


def test_prefere_o_video_anotado_pela_visao(tmp_path):
    (tmp_path / "orig").mkdir(); (tmp_path / "anot").mkdir()
    (tmp_path / "orig" / "visao_geral_andador.mp4").write_bytes(b"\x00")
    c = [x for x in vg.CENARIOS if x.id == "andador"][0]
    assert vg.video_do_cenario(c, tmp_path / "orig", tmp_path / "anot").name == "visao_geral_andador.mp4"
    (tmp_path / "anot" / "andador_01_anotado.mp4").write_bytes(b"\x00")
    assert vg.video_do_cenario(c, tmp_path / "orig", tmp_path / "anot").name == "andador_01_anotado.mp4"
