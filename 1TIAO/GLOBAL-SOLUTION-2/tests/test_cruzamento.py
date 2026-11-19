"""Player do Estudo A (src/operador/cruzamento.py): números vêm do resumo do estudo, não de valores ilustrativos."""
import json

import pytest

import cruzamento as cz


@pytest.mark.parametrize("cena,sem,com", [("pedestre", "100%", "0%"), ("ambulancia", "49,3 s", "40,6 s")])
def test_metricas_vem_do_resumo(cena, sem, com):
    dados, met = cz.carregar(cena)
    assert (met["sem"], met["com"]) == (sem, com)
    assert len(dados["sem"]) == len(dados["com"]) > 100


def test_cena_da_ambulancia_tem_ambulancia_nos_dois_lados():
    dados, _ = cz.carregar("ambulancia")
    for lado in ("sem", "com"):
        assert any(c[4] == "ambulancia" for q in dados[lado] for c in q["carros"])


def test_html_leva_os_dados_e_os_dois_lados():
    dados, met = cz.carregar("pedestre")
    h = cz.html_cruzamento(dados, met)
    assert "Com a BetterWay" in h and "Hoje" in h and "Resultado esperado de simulação" in h
    assert json.dumps(met["rotulo"], ensure_ascii=False) in h


def test_cena_do_transito_mostra_menos_carros_parados_com_a_betterway():
    dados, met = cz.carregar("transito")
    assert cz.parados_na_avenida(dados["com"]) < cz.parados_na_avenida(dados["sem"])
    assert "faixa vazia" in met["nota"]


def test_cena_do_acidente_evitado_nunca_libera_carros_com_gente_na_faixa():
    dados, met = cz.carregar("conflito")
    em_risco = lambda q: q["verde_avenida"] and any(p[4] for p in q["pessoas"])  # noqa: E731
    assert any(em_risco(q) for q in dados["sem"])
    assert not any(em_risco(q) for q in dados["com"])
    assert (met["sem"], met["com"]) == ("5,6", "0")


def test_modo_compacto_so_na_visao_geral():
    dados, met = cz.carregar("transito")
    assert 'class="tudo compacto"' in cz.html_cruzamento(dados, met, compacto=True)
    assert 'class="tudo compacto"' not in cz.html_cruzamento(dados, met)


def test_compacto_aproxima_o_cruzamento():
    dados, met = cz.carregar("conflito")
    h = cz.html_cruzamento(dados, met, compacto=True)
    assert 'viewBox="-20 -14 40 28"' in h and 'viewBox="-30 -21 60 42"' not in h
