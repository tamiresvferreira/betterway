"""Testes do modelo de risco de OCORRÊNCIA de atropelamento (notebook 06) e da parte nova da risco().

Rodar a partir da raiz do repositório:  python -m pytest tests -v
"""
import math

import pandas as pd
import pytest

import risco as rv


# ---------------------------------------------------------------- variáveis por célula
def test_variaveis_celula_resume_o_treino(treino_sintetico):
    tc = rv.variaveis_celula(rv.construir_tabelas(treino_sintetico, eps_m=100, min_samples=8))
    a, b = rv.celula([-23.55], [-46.63])[0], rv.celula([-23.70], [-46.70])[0]
    assert tc.loc[[a]].iloc[0].tolist() == pytest.approx([math.log1p(10), 1, 14, 0])
    assert tc.loc[[b]].iloc[0].tolist() == pytest.approx([math.log1p(1), 0, 0, 1])


def test_variaveis_celula_por_ano_divide_historico_e_peso(treino_sintetico):
    tc = rv.variaveis_celula(rv.construir_tabelas(treino_sintetico, eps_m=100, min_samples=8), anos=2)
    a = rv.celula([-23.55], [-46.63])[0]
    # 10 atropelamentos em 2 anos → 5 por ano; peso 14 em 2 anos → 7 por ano
    assert tc.loc[[a]].iloc[0].tolist() == pytest.approx([math.log1p(5), 1, 7, 0])


def test_celula_sem_historico_recebe_zeros(treino_sintetico):
    tc = rv.variaveis_celula(rv.construir_tabelas(treino_sintetico, eps_m=100, min_samples=8))
    v = rv.montar_variaveis_risco([(0, 0)], [18], [0], [1], tc)
    assert v[["hist_log", "em_grupo", "peso_grupo", "rodovia"]].iloc[0].tolist() == [0, 0, 0, 0]
    assert v.columns.tolist() == rv.RISCO_VARIAVEIS
    assert v["hora_sin"].iloc[0] == pytest.approx(-1.0)
    assert v["hora_cos2"].iloc[0] == pytest.approx(-1.0)   # 18h no 2º harmônico: 2·270° = 540° → cosseno -1


# ---------------------------------------------------------------- exposição e contagens
def test_chuva_por_hora_desloca_uma_hora():
    s = pd.Series([0.0, 1.5], index=pd.to_datetime(["2024-01-01 01:00", "2024-01-01 02:00"]))
    h = rv.chuva_por_hora(s)
    assert h.index.tolist() == list(pd.to_datetime(["2024-01-01 00:00", "2024-01-01 01:00"]))
    assert h.tolist() == [0.0, 1.5]


def test_exposicao_conta_horas_por_combinacao():
    # sábado 06/01/2024 23h (fds, seco), domingo 07/01 23h (fds, chuva 0,5), segunda 08/01 0h (útil, seco)
    idx = pd.to_datetime(["2024-01-06 23:00", "2024-01-07 23:00", "2024-01-08 00:00"])
    e = rv.exposicao(pd.Series([0.0, 0.5, 0.1], index=idx), "2024-01-06", "2024-01-08")
    e = e.set_index(["hora", "fim_de_semana", "chovendo"])["horas"].to_dict()
    assert e == {(23, 1, 0): 1, (23, 1, 1): 1, (0, 0, 0): 1}


def test_exposicao_ignora_horas_sem_valor_de_chuva():
    idx = pd.to_datetime(["2024-01-08 10:00"])  # 11h não tem valor
    e = rv.exposicao(pd.Series([0.0], index=idx), "2024-01-08", "2024-01-08")
    assert e["horas"].sum() == 1


def test_contagens_agrupa_por_celula_e_combinacao():
    ev = pd.DataFrame({"latitude": [-23.551, -23.551, -23.551, -23.701],
                       "longitude": [-46.631, -46.631, -46.631, -46.701],
                       "quando": pd.to_datetime(["2024-01-08 18:10", "2024-01-09 18:50", "2024-01-13 18:00",
                                                 "2024-01-08 03:00"]),
                       "chuva_mm": [0.0, 0.0, 0.0, 2.0]})
    c = rv.contagens(ev).set_index(["celula", "hora", "fim_de_semana", "chovendo"])["n"].to_dict()
    # -23.551/0.005 = -4710.2 → -4711 ; -46.631/0.005 = -9326.2 → -9327 ; -23.701 → -4741 ; -46.701 → -9341
    assert c == {((-4711, -9327), 18, 0, 0): 2, ((-4711, -9327), 18, 1, 0): 1, ((-4741, -9341), 3, 0, 1): 1}


# ---------------------------------------------------------------- risco() com risco de ocorrência
from datetime import datetime
from zoneinfo import ZoneInfo

LARGO = (-23.54231, -46.61655)


def test_largo_devolve_probabilidade_de_atropelamento_valida():
    r = rv.risco(*LARGO, datetime(2026, 11, 10, 18, 30), 0.0)
    assert 0.0 < r["probabilidade_atropelamento_1h"] < 1.0
    assert r["nivel"] in {"baixo", "medio", "alto"}
    assert r["risco_relativo"] > 0
    assert r["probabilidade_atropelamento_fatal_1h"] == pytest.approx(
        r["probabilidade_atropelamento_1h"] * r["probabilidade_fatal"], abs=1e-3)


def test_dia_util_18h_tem_mais_risco_que_4h():
    a = rv.risco(*LARGO, datetime(2026, 11, 10, 18, 0), 0.0)
    b = rv.risco(*LARGO, datetime(2026, 11, 10, 4, 0), 0.0)
    assert a["probabilidade_atropelamento_1h"] > b["probabilidade_atropelamento_1h"]


def test_largo_tem_mais_risco_que_celula_sem_historico():
    a = rv.risco(*LARGO, datetime(2026, 11, 10, 18, 0), 0.0)
    b = rv.risco(-23.98, -46.80, datetime(2026, 11, 10, 18, 0), 0.0)   # extremo sul, sem histórico
    assert a["probabilidade_atropelamento_1h"] > b["probabilidade_atropelamento_1h"]


def test_fora_de_sp_tem_risco_baixo_sem_grupo():
    r = rv.risco(-22.90, -43.20, datetime(2026, 11, 10, 18, 0), 0.0)
    assert r["cluster_id"] is None
    assert 0.0 <= r["probabilidade_atropelamento_1h"] < 1.0
    assert r["nivel"] == "baixo"


def test_quando_com_fuso_e_aceito():
    r = rv.risco(*LARGO, datetime(2026, 11, 10, 18, 0, tzinfo=ZoneInfo("America/Sao_Paulo")), 0.0)
    assert 0.0 < r["probabilidade_atropelamento_1h"] < 1.0


def test_chuva_muito_alta_nao_quebra():
    r = rv.risco(*LARGO, datetime(2026, 11, 10, 18, 0), 300.0)
    assert 0.0 <= r["probabilidade_atropelamento_1h"] <= 1.0
    assert 0.0 <= r["probabilidade_fatal"] <= 1.0


# ---------------------------------------------------------------- revisão final: mesma régua para 1 e 2 anos
def test_tabela_celulas_com_dois_anos_usa_a_mesma_regua_de_um_ano():
    # ponto C com 5 não fatais por ano: peso 5 < 8 → não é grupo com 1 ano. Com 2 anos (peso 10) também não pode
    # virar grupo, senão "em_grupo" muda de sentido entre o treino (1 ano) e a produção (2 anos).
    um_ano = pd.DataFrame([{"latitude": -23.60, "longitude": -46.60, "fatal": False, "tipo_via": "VIAS URBANAS"}] * 5)
    dois_anos = pd.concat([um_ano, um_ano], ignore_index=True)
    c = rv.celula([-23.60], [-46.60])[0]
    t1, t2 = rv.tabela_celulas(um_ano, anos=1), rv.tabela_celulas(dois_anos, anos=2)
    assert t1.loc[[c]].iloc[0].tolist() == pytest.approx(t2.loc[[c]].iloc[0].tolist())
    assert t2.loc[[c], "em_grupo"].iloc[0] == 0
