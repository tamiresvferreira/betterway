"""Visão geral em quatro cenários: ordem, navegação pela seta e procura do vídeo de cada cenário."""
from pathlib import Path

import pytest

import visao_geral as vg

EVID_A = Path(__file__).resolve().parents[1] / "docs" / "evidencias" / "estudo_a"


def test_quatro_cenarios_na_ordem_dos_pilares():
    assert [c.id for c in vg.CENARIOS] == ["conflito", "transito", "ambulancia", "pedestre"]
    assert [c.verbo for c in vg.CENARIOS] == ["to live", "to move", "to move", "to be free"]


def test_cada_cenario_tem_a_simulacao_exportada():
    for c in vg.CENARIOS:
        assert (EVID_A / f"cena_{c.cena}.json").exists(), c.cena


def test_textos_sem_travessao():
    for c in vg.CENARIOS:
        assert "—" not in c.titulo + c.texto


@pytest.mark.parametrize("i, esperado", [(0, 1), (1, 2), (2, 3), (3, 0)])
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
