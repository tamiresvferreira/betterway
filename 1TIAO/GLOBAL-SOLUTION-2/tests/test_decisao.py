"""Regras da central (src/central/decisao.py) — spec docs/specs/2026-11-16-central-design.md §4."""
from datetime import datetime

import pytest

import decisao as d
import mensagens as m

SEG_7H = datetime(2026, 11, 16, 7, 0)      # segunda-feira, horário de escola
SEG_10H = datetime(2026, 11, 16, 10, 0)    # segunda-feira, fora das janelas
SAB_7H = datetime(2026, 11, 21, 7, 0)      # sábado


def E(**k):
    return d.Entradas(quando=k.pop("quando", SEG_10H), **k)


def test_normal_sem_nada():
    r = d.decidir(E())
    assert (r.modo, r.campos) == ("normal", {})
    assert m.validar_comando(m.comando(r.modo, **r.campos)) == []


@pytest.mark.parametrize("mm, modo, alag", [(2.4, "normal", None), (2.5, "chuva", False), (9.9, "chuva", False),
                                             (10.0, "chuva", True)])
def test_limiares_de_chuva(mm, modo, alag):
    r = d.decidir(E(chuva_mm_h=mm))
    assert r.modo == modo and r.campos.get("alagamento") == alag


def test_chuva_simulada_aparece_no_motivo():
    assert "SIMULADA" in d.decidir(E(chuva_mm_h=6.0, chuva_simulada=True)).motivo
    assert "SIMULADA" not in d.decidir(E(chuva_mm_h=6.0)).motivo


def test_escola_so_nas_janelas_de_dia_util():
    assert d.decidir(E(quando=SEG_7H)).modo == "escola"
    assert d.decidir(E(quando=SAB_7H)).modo == "normal"
    assert d.em_horario_escola(datetime(2026, 11, 16, 6, 45))
    assert not d.em_horario_escola(datetime(2026, 11, 16, 7, 31))
    assert d.em_horario_escola(datetime(2026, 11, 16, 12, 0)) and d.em_horario_escola(datetime(2026, 11, 16, 18, 0))


def test_pedestre_com_faixa_ocupada():
    r = d.decidir(E(pessoas_na_faixa=3))
    assert r.modo == "pedestre" and r.campos == {"faixa_ocupada": True}


@pytest.mark.parametrize("eta, modo", [(61, "normal"), (60, "ambulancia"), (0, "ambulancia")])
def test_ambulancia_a_60_s(eta, modo):
    r = d.decidir(E(ambulancia_eta_s=eta))
    assert r.modo == modo
    if modo == "ambulancia":
        assert r.campos == {"eta_s": eta} and "SIMULADA" in r.motivo


def test_ambulancia_passou_manda_fim():
    r = d.decidir(E(ambulancia_passou=True))
    assert (r.modo, r.campos) == ("ambulancia", {"fim": True})


def test_prioridade():
    tudo = dict(quando=SEG_7H, chuva_mm_h=12.0, pessoas_na_faixa=2)
    assert d.decidir(E(ambulancia_eta_s=20, **tudo)).modo == "ambulancia"
    assert d.decidir(E(**tudo)).modo == "chuva"
    assert d.decidir(E(quando=SEG_7H, pessoas_na_faixa=2)).modo == "escola"


def test_falta_de_dado_nao_vira_fato():
    """Revisão: sem a chuva (API fora), o motivo não pode dizer 'sem chuva'."""
    assert "sem dado" in d.decidir(E(chuva_mm_h=None)).motivo
    assert "sem dado" not in d.decidir(E(chuva_mm_h=0.0)).motivo


def test_camera_ve_andador_e_pede_tempo_extra():
    r = d.decidir(E(pessoas_na_faixa=3, pcd_na_faixa=2))
    assert r.modo == "pedestre" and r.campos == {"faixa_ocupada": True, "estendida": True}
    assert "auxílio de mobilidade" in r.motivo
