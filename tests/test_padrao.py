"""Padrão que se repete (src/operador/padrao.py): a situação de agora parece com a dos atropelamentos do local?"""
from datetime import datetime

import pandas as pd

import padrao as pd_

TER_7H = datetime(2026, 11, 17, 7, 20)      # terça
DOM_7H = datetime(2026, 11, 22, 7, 20)      # domingo


def _hist(linhas):
    return pd.DataFrame(linhas, columns=["data_sinistro", "hora", "chuva_mm"])


# 20 atropelamentos: 8 em dia útil às 7h (pico), o resto espalhado
HIST = _hist([("2024-03-05", 7, 0.0)] * 6 + [("2024-03-06", 8, 2.0)] * 2 +
             [("2024-03-0%d" % (4 + i % 5), 10 + i, 0.0) for i in range(10)] + [("2024-03-10", 15, 0.0)] * 2)


def test_janela_de_pico_em_dia_util_e_padrao():
    p = pd_.padrao_agora(HIST, TER_7H)
    assert p.casos_na_janela == 8 and p.total == 20
    assert p.se_repete and p.vezes_a_media >= 1.5
    assert "8 dos 20" in p.texto and "dia útil" in p.texto and "6h e 8h" in p.texto


def test_domingo_de_manha_nao_e_padrao():
    p = pd_.padrao_agora(HIST, DOM_7H)
    assert p.casos_na_janela == 0 and not p.se_repete


def test_poucos_casos_nao_viram_padrao():
    p = pd_.padrao_agora(_hist([("2024-03-05", 7, 0.0)] * 2), TER_7H)
    assert p.casos_na_janela == 2 and not p.se_repete


def test_chuva_agora_conta_quantos_foram_com_chuva():
    p = pd_.padrao_agora(HIST, TER_7H, chuva_mm_h=4.0)
    assert p.casos_com_chuva == 2 and "2 com chuva" in p.texto
    assert "com chuva" not in pd_.padrao_agora(HIST, TER_7H, chuva_mm_h=0.0).texto


def test_historico_vazio():
    p = pd_.padrao_agora(_hist([]), TER_7H)
    assert p.total == 0 and not p.se_repete and p.texto
