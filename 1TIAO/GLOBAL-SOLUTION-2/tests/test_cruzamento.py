"""Player do Estudo A (src/operador/cruzamento.py): números vêm do resumo do estudo, não de valores ilustrativos."""
import json

import pytest

import cruzamento as cz


@pytest.mark.parametrize("cena,sem,com", [("pedestre", "100%", "0%"), ("ambulancia", "46,9 s", "40,7 s")])
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
