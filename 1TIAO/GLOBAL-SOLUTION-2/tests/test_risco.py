"""Testes da função risco() e das variáveis que ela monta (as mesmas do treino do classificador).

Rodar a partir de 1TIAO/GLOBAL-SOLUTION-2/:  python -m pytest tests -v
"""
import math
from datetime import datetime

import pandas as pd
import pytest

import risco as rv

TERCA_18H30 = datetime(2026, 11, 10, 18, 30)   # 10/11/2026 é terça-feira
SABADO_03H = datetime(2026, 11, 14, 3, 0)      # 14/11/2026 é sábado
LARGO_CONCORDIA = (-23.54231, -46.61655)       # referência usada no notebook 04
RIO_DE_JANEIRO = (-22.90, -43.20)


# ---------------------------------------------------------------- variáveis de tempo e chuva
def test_variaveis_tempo_codificam_hora_dia_e_mes():
    v = rv.variaveis_tempo(pd.Series([TERCA_18H30, SABADO_03H]))
    # 18h = 3/4 da volta: seno -1, cosseno 0;  3h = 1/8 da volta: seno = cosseno = 0,7071
    assert v["hora_sin"].tolist() == pytest.approx([-1.0, 0.70711], abs=1e-4)
    assert v["hora_cos"].tolist() == pytest.approx([0.0, 0.70711], abs=1e-4)
    assert v["dia_semana"].tolist() == [1, 5]          # segunda = 0
    assert v["fim_de_semana"].tolist() == [0, 1]
    # novembro (11): ângulo 2π·11/12 → seno -0,5, cosseno 0,866
    assert v["mes_sin"].tolist() == pytest.approx([-0.5, -0.5], abs=1e-4)
    assert v["mes_cos"].tolist() == pytest.approx([0.86603, 0.86603], abs=1e-4)


def test_chovendo_comeca_em_0_2_mm():
    v = rv.variaveis_chuva(pd.Series([0.0, 0.19, 0.2, 10.0]))
    assert v["chovendo"].tolist() == [0, 0, 1, 1]
    assert v["chuva_mm"].tolist() == [0.0, 0.19, 0.2, 10.0]


# ---------------------------------------------------------------- variáveis do local (sem vazamento)
@pytest.fixture
def treino_sintetico():
    # 10 atropelamentos no mesmo ponto A (2 fatais) + 1 fatal isolado em B, longe.
    a = [{"latitude": -23.55, "longitude": -46.63, "fatal": i < 2, "tipo_via": "VIAS URBANAS"} for i in range(10)]
    b = [{"latitude": -23.70, "longitude": -46.70, "fatal": True, "tipo_via": "ESTRADAS E RODOVIAS"}]
    return pd.DataFrame(a + b)


def test_ponto_novo_no_grupo_usa_letalidade_suavizada_do_grupo(treino_sintetico):
    tab = rv.construir_tabelas(treino_sintetico, eps_m=100, min_samples=8)
    v = rv.variaveis_local([-23.55], [-46.63], tab)
    # peso = 8 não fatais + 3×2 fatais = 14; taxa global = 3/11
    # letalidade suavizada (K=20) = (2 + 20·3/11) / (10 + 20) = 0,24848
    assert v["em_grupo"].tolist() == [1]
    assert v["peso_grupo"].tolist() == [14]
    assert v["n_hist_local"].tolist() == [10]
    assert v["let_local"].tolist() == pytest.approx([0.24848], abs=1e-4)


def test_linha_de_treino_nao_enxerga_o_proprio_rotulo(treino_sintetico):
    tab = rv.construir_tabelas(treino_sintetico, eps_m=100, min_samples=8)
    # linha 0 é fatal e está no grupo: tirando ela, ficam 9 casos, 1 fatal, peso 11
    # letalidade = (1 + 20·3/11) / (9 + 20) = 0,22257
    v = rv.variaveis_local([-23.55], [-46.63], tab, indices_treino=[0])
    assert v["peso_grupo"].tolist() == [11]
    assert v["n_hist_local"].tolist() == [9]
    assert v["let_local"].tolist() == pytest.approx([0.22257], abs=1e-4)


def test_ponto_isolado_fica_fora_de_grupo_e_cai_na_taxa_global(treino_sintetico):
    tab = rv.construir_tabelas(treino_sintetico, eps_m=100, min_samples=8)
    # B tem peso 3 < 8: é ruído. Sem ele próprio, a célula fica vazia → taxa global 3/11
    v = rv.variaveis_local([-23.70], [-46.70], tab, indices_treino=[10])
    assert v["em_grupo"].tolist() == [0]
    assert v["n_hist_local"].tolist() == [0]
    assert v["let_local"].tolist() == pytest.approx([3 / 11], abs=1e-4)


def test_tipo_de_via_do_local_vem_dos_atropelamentos_vizinhos(treino_sintetico):
    tab = rv.construir_tabelas(treino_sintetico, eps_m=100, min_samples=8)
    # ponto novo a ~50 m de B (rodovia) e ponto novo em A (via urbana)
    v = rv.variaveis_local([-23.7004, -23.55], [-46.70, -46.63], tab)
    assert v["rodovia_local"].tolist() == [1, 0]


# ---------------------------------------------------------------- função risco() (exigidos no plano)
def test_largo_da_concordia_terca_18h30_sem_chuva_devolve_dict_valido():
    r = rv.risco(*LARGO_CONCORDIA, TERCA_18H30, 0.0)
    assert set(r) >= {"probabilidade_fatal", "nivel", "cluster_id", "rank_prioridade", "motivos"}
    assert 0.0 <= r["probabilidade_fatal"] <= 1.0
    assert r["nivel"] in {"baixo", "medio", "alto"}
    assert isinstance(r["cluster_id"], int)
    assert isinstance(r["rank_prioridade"], int)
    assert isinstance(r["motivos"], list) and all(isinstance(m, str) for m in r["motivos"])


def test_mesmo_local_sabado_madrugada_com_chuva_tem_probabilidade_maior():
    base = rv.risco(*LARGO_CONCORDIA, TERCA_18H30, 0.0)
    pior = rv.risco(*LARGO_CONCORDIA, SABADO_03H, 10.0)
    assert pior["probabilidade_fatal"] > base["probabilidade_fatal"]
    assert "madrugada" in pior["motivos"] and "chuva" in pior["motivos"]


def test_ponto_fora_de_sao_paulo_nao_quebra_e_fica_sem_grupo():
    r = rv.risco(*RIO_DE_JANEIRO, TERCA_18H30, 0.0)
    assert r["cluster_id"] is None
    assert r["rank_prioridade"] is None
    assert 0.0 <= r["probabilidade_fatal"] <= 1.0


@pytest.mark.parametrize("lat, lon, chuva", [
    (-23.54, -46.61, -1.0),          # chuva negativa
    (95.0, -46.61, 0.0),             # latitude impossível
    (-23.54, -200.0, 0.0),           # longitude impossível
    (math.nan, -46.61, 0.0),         # latitude ausente
    (-23.54, -46.61, math.inf),      # chuva infinita
])
def test_entradas_invalidas_levantam_value_error(lat, lon, chuva):
    with pytest.raises(ValueError):
        rv.risco(lat, lon, TERCA_18H30, chuva)


def test_quando_precisa_ser_datetime():
    with pytest.raises(ValueError):
        rv.risco(*LARGO_CONCORDIA, "2026-11-10 18:30", 0.0)
