"""Risco de um atropelamento ser fatal (Estudo B, Via Segura SP).

Uso pela central (Python) e, via central, pelo nó ESP32:

    from risco import risco
    risco(-23.5423, -46.6166, datetime(2026, 11, 10, 18, 30), chuva_mm=0.0)
    # {'probabilidade_fatal': 0.05, 'nivel': 'medio', 'cluster_id': 139, 'rank_prioridade': 41, ...}

As funções de variáveis (variaveis_tempo, variaveis_chuva, construir_tabelas, variaveis_local) são as MESMAS usadas
no treino (notebook 05_classificador_gravidade.ipynb), para o modelo receber em produção exatamente o que viu no
treino. O modelo e as tabelas ficam em models/modelo_gravidade.joblib e são carregados uma vez só (cache).
"""
from __future__ import annotations

import math
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import haversine_distances
from sklearn.neighbors import BallTree

R_TERRA = 6_371_000
EPS_M = 100                 # mesmo eps do DBSCAN do notebook 03
MIN_SAMPLES = 8             # em peso (fatal = 3)
LIMIAR_CHUVA_MM = 0.2       # chovendo = chuva_mm >= 0,2 mm na hora
CELULA_GRAUS = 0.005        # célula de ~500 m (a mesma do notebook 01)
K_SUAVIZACAO = 20           # letalidade local suavizada: (fatais + K·taxa_global) / (n + K)
RAIO_TIPO_VIA_M = 150       # tipo de via do local = maioria dos atropelamentos de treino neste raio
INDICE_SEM_GRUPO = 30.0     # índice CET atribuído a quem não está em grupo (acima do maior índice observado)
CAMINHO_MODELO = Path(__file__).resolve().parents[2] / "models" / "modelo_gravidade.joblib"

VARIAVEIS = ["hora_sin", "hora_cos", "dia_semana", "fim_de_semana", "mes_sin", "mes_cos",
             "chovendo", "chuva_mm", "rodovia_local", "em_grupo", "peso_grupo", "indice_cet_grupo",
             "let_local", "n_hist_local"]


# ------------------------------------------------------------------------------------------ tempo e chuva
def variaveis_tempo(quando: pd.Series) -> pd.DataFrame:
    """Hora (seno/cosseno), dia da semana (segunda = 0), fim de semana e mês (seno/cosseno)."""
    q = pd.to_datetime(pd.Series(quando)).reset_index(drop=True)
    hora, mes = q.dt.hour.to_numpy(), q.dt.month.to_numpy()
    return pd.DataFrame({
        "hora_sin": np.sin(2 * np.pi * hora / 24), "hora_cos": np.cos(2 * np.pi * hora / 24),
        "dia_semana": q.dt.day_of_week.to_numpy(), "fim_de_semana": (q.dt.day_of_week >= 5).astype(int).to_numpy(),
        "mes_sin": np.sin(2 * np.pi * mes / 12), "mes_cos": np.cos(2 * np.pi * mes / 12),
    })


def variaveis_chuva(chuva_mm: pd.Series) -> pd.DataFrame:
    c = pd.Series(chuva_mm, dtype=float).reset_index(drop=True)
    return pd.DataFrame({"chovendo": (c >= LIMIAR_CHUVA_MM).astype(int), "chuva_mm": c})


# ------------------------------------------------------------------------------------------ local
def _rad(lat, lon) -> np.ndarray:
    return np.radians(np.c_[np.asarray(lat, float), np.asarray(lon, float)])


def celula(lat, lon) -> list[tuple[int, int]]:
    """Célula de ~500 m (grade de 0,005°) de cada ponto."""
    return list(zip(np.floor(np.asarray(lat, float) / CELULA_GRAUS).astype(int).tolist(),
                    np.floor(np.asarray(lon, float) / CELULA_GRAUS).astype(int).tolist()))


_celula = celula


# ------------------------------------------------------------------------------------------ risco de ocorrência
def chuva_por_hora(serie: pd.Series) -> pd.Series:
    """Série do Open-Meteo (carimbo = fim da hora) → índice = início da hora. Ex.: valor das 19h vale para 18h–19h."""
    return pd.Series(serie.to_numpy(), index=pd.DatetimeIndex(serie.index) - pd.Timedelta(hours=1))


def exposicao(chuva_hora: pd.Series, inicio: str, fim: str) -> pd.DataFrame:
    """Horas existentes por hora do dia × fim de semana × chovendo, entre as datas inicio e fim (inclusivas).

    Só conta horas que têm valor de chuva (a última hora da série, sem o valor seguinte, fica de fora).
    """
    idx = pd.DatetimeIndex(chuva_hora.index)
    m = (idx >= pd.Timestamp(inicio)) & (idx < pd.Timestamp(fim) + pd.Timedelta(days=1)) & chuva_hora.notna().to_numpy()
    d = pd.DataFrame({"hora": idx[m].hour, "fim_de_semana": (idx[m].day_of_week >= 5).astype(int),
                      "chovendo": (chuva_hora.to_numpy()[m] >= LIMIAR_CHUVA_MM).astype(int)})
    return d.groupby(["hora", "fim_de_semana", "chovendo"]).size().rename("horas").reset_index()


RISCO_VARIAVEIS = ["hora_sin", "hora_cos", "hora_sin2", "hora_cos2", "fim_de_semana", "chovendo",
                   "hist_log", "em_grupo", "peso_grupo", "rodovia"]
_VARIAVEIS_CELULA = ["hist_log", "em_grupo", "peso_grupo", "rodovia"]


def variaveis_celula(tabelas: dict, anos: float = 1.0) -> pd.DataFrame:
    """Resumo do histórico por célula: log1p(atropelamentos por ano), tem ponto em grupo do DBSCAN, maior peso de grupo
    (por ano) com ponto na célula e se a maioria dos pontos é em rodovia. `tabelas` vem de construir_tabelas;
    `anos` = quantos anos o histórico cobre (deixa 1 e 2 anos de histórico na mesma escala)."""
    rot = tabelas["rotulos"]
    peso = np.array([tabelas["grupos"][int(g)]["peso"] if g >= 0 else 0 for g in rot])
    d = pd.DataFrame({"celula": pd.Index(tabelas["celula_pt"], tupleize_cols=False), "em_grupo": (rot >= 0).astype(int),
                      "peso_grupo": peso, "rodovia": tabelas["rodovia_pt"].astype(float)})
    g = d.groupby("celula").agg(n=("em_grupo", "size"), em_grupo=("em_grupo", "max"),
                                peso_grupo=("peso_grupo", "max"), rodovia=("rodovia", "mean"))
    g["hist_log"] = np.log1p(g["n"] / anos)
    g["peso_grupo"] = g["peso_grupo"] / anos
    g["rodovia"] = (g["rodovia"] > 0.5).astype(int)
    g.index = pd.Index(list(g.index), tupleize_cols=False)
    return g[_VARIAVEIS_CELULA]


def montar_variaveis_risco(celulas: list, hora, fim_de_semana, chovendo, tab_celula: pd.DataFrame) -> pd.DataFrame:
    """Variáveis do modelo de risco (RISCO_VARIAVEIS). Célula fora de tab_celula → variáveis de local zeradas."""
    h = np.asarray(hora, float)
    loc = tab_celula.reindex(pd.Index(list(celulas), tupleize_cols=False)).fillna(0).reset_index(drop=True)
    v = pd.DataFrame({"hora_sin": np.sin(2 * np.pi * h / 24), "hora_cos": np.cos(2 * np.pi * h / 24),
                      "hora_sin2": np.sin(4 * np.pi * h / 24), "hora_cos2": np.cos(4 * np.pi * h / 24),
                      "fim_de_semana": np.asarray(fim_de_semana, int), "chovendo": np.asarray(chovendo, int)})
    return pd.concat([v, loc], axis=1)[RISCO_VARIAVEIS]


def contagens(eventos: pd.DataFrame) -> pd.DataFrame:
    """Atropelamentos por célula × hora × fim de semana × chovendo. `eventos`: latitude, longitude, quando, chuva_mm."""
    q = pd.to_datetime(eventos["quando"])
    d = pd.DataFrame({"celula": celula(eventos["latitude"], eventos["longitude"]), "hora": q.dt.hour.to_numpy(),
                      "fim_de_semana": (q.dt.day_of_week >= 5).astype(int).to_numpy(),
                      "chovendo": (eventos["chuva_mm"].to_numpy() >= LIMIAR_CHUVA_MM).astype(int)})
    return d.groupby(["celula", "hora", "fim_de_semana", "chovendo"]).size().rename("n").reset_index()


def construir_tabelas(treino: pd.DataFrame, eps_m: float = EPS_M, min_samples: int = MIN_SAMPLES) -> dict:
    """Tabelas do local feitas SÓ com o treino: DBSCAN (peso 3 p/ fatal), contagens por grupo e por célula.

    `treino` precisa de latitude, longitude, fatal e tipo_via.
    """
    t = treino.reset_index(drop=True)
    fatal = t["fatal"].astype(bool).to_numpy()
    peso_pt = np.where(fatal, 3, 1)
    X = _rad(t["latitude"], t["longitude"])
    rotulos = DBSCAN(eps=eps_m / R_TERRA, min_samples=min_samples, metric="haversine",
                     algorithm="ball_tree").fit_predict(X, sample_weight=peso_pt)
    grupos = {}
    for g in np.unique(rotulos[rotulos >= 0]):
        m = rotulos == g
        ext = float(haversine_distances(X[m]).max() * R_TERRA) if m.sum() > 1 else 0.0
        grupos[int(g)] = {"n": int(m.sum()), "fatais": int(fatal[m].sum()), "peso": int(peso_pt[m].sum()),
                          "extensao_m": ext}
    cel = pd.DataFrame({"celula": _celula(t["latitude"], t["longitude"]), "fatal": fatal})
    celulas = cel.groupby("celula")["fatal"].agg(["size", "sum"]).rename(columns={"size": "n", "sum": "fatais"})
    agrupados = np.flatnonzero(rotulos >= 0)
    return {
        "eps_m": eps_m, "min_samples": min_samples, "taxa_global": float(fatal.mean()),
        "rotulos": rotulos, "fatal": fatal, "peso_pt": peso_pt, "celula_pt": cel["celula"].tolist(),
        "grupos": grupos, "celulas": {k: (int(r.n), int(r.fatais)) for k, r in celulas.iterrows()},
        "arvore_agrupados": BallTree(X[agrupados], metric="haversine") if len(agrupados) else None,
        "rotulo_agrupados": rotulos[agrupados],
        "arvore_todos": BallTree(X, metric="haversine"),
        "rodovia_pt": t["tipo_via"].eq("ESTRADAS E RODOVIAS").to_numpy(),
    }


def variaveis_local(lat, lon, tabelas: dict, indices_treino=None) -> pd.DataFrame:
    """Variáveis do local para pontos (lat, lon).

    indices_treino: posição de cada ponto na tabela de treino, quando o ponto É uma linha do treino. Nesse caso o
    próprio registro sai das contagens (leave-one-out), para a letalidade local não conter o rótulo da linha.
    """
    tab = tabelas
    X = _rad(lat, lon)
    n_pts = len(X)
    proprio = np.full(n_pts, -1) if indices_treino is None else np.asarray(indices_treino, int)
    p = tab["taxa_global"]

    # grupo: o ponto agrupado de treino mais próximo, se estiver a menos de eps
    grupo = np.full(n_pts, -1)
    if tab["arvore_agrupados"] is not None:
        d, j = tab["arvore_agrupados"].query(X, k=1)
        perto = d[:, 0] * R_TERRA <= tab["eps_m"]
        grupo[perto] = tab["rotulo_agrupados"][j[perto, 0]]

    # tipo de via do local: maioria dos atropelamentos de treino a até 150 m (sem contar o próprio)
    viz = tab["arvore_todos"].query_radius(X, r=RAIO_TIPO_VIA_M / R_TERRA)
    rodovia = []
    for i, idx in enumerate(viz):
        idx = idx[idx != proprio[i]]
        rodovia.append(int(len(idx) > 0 and tab["rodovia_pt"][idx].mean() > 0.5))

    linhas = []
    for i, (g, c) in enumerate(zip(grupo, _celula(lat, lon))):
        k = proprio[i]
        if g >= 0:
            info = tab["grupos"][int(g)]
            n, f, peso = info["n"], info["fatais"], info["peso"]
            if k >= 0 and tab["rotulos"][k] == g:                    # o próprio registro está no grupo
                n, f, peso = n - 1, f - int(tab["fatal"][k]), peso - int(tab["peso_pt"][k])
            indice = max(info["extensao_m"], 20) / peso if peso > 0 else INDICE_SEM_GRUPO
            linhas.append({"em_grupo": 1, "peso_grupo": peso, "indice_cet_grupo": indice,
                           "let_local": (f + K_SUAVIZACAO * p) / (n + K_SUAVIZACAO), "n_hist_local": n})
        else:
            n, f = tab["celulas"].get(c, (0, 0))
            if k >= 0 and tab["celula_pt"][k] == c:
                n, f = n - 1, f - int(tab["fatal"][k])
            linhas.append({"em_grupo": 0, "peso_grupo": 0, "indice_cet_grupo": INDICE_SEM_GRUPO,
                           "let_local": (f + K_SUAVIZACAO * p) / (n + K_SUAVIZACAO), "n_hist_local": n})
    out = pd.DataFrame(linhas)
    out.insert(0, "rodovia_local", rodovia)
    return out


def montar_variaveis(lat, lon, quando, chuva_mm, tabelas: dict, indices_treino=None) -> pd.DataFrame:
    """Todas as variáveis do modelo, na ordem de VARIAVEIS."""
    v = pd.concat([variaveis_tempo(quando), variaveis_chuva(chuva_mm),
                   variaveis_local(lat, lon, tabelas, indices_treino)], axis=1)
    return v[VARIAVEIS]


# ------------------------------------------------------------------------------------------ risco()
@lru_cache(maxsize=1)
def _pacote(caminho: str = str(CAMINHO_MODELO)) -> dict:
    """Modelo + tabelas, carregados do disco uma vez só por processo."""
    import joblib
    if not Path(caminho).exists():
        raise FileNotFoundError(f"{caminho} não existe: rode o notebook 05_classificador_gravidade.ipynb")
    return joblib.load(caminho)


def _numero(nome: str, valor, minimo: float, maximo: float) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float, np.integer, np.floating)):
        raise ValueError(f"{nome} precisa ser número, recebeu {valor!r}")
    v = float(valor)
    if not math.isfinite(v) or not (minimo <= v <= maximo):
        raise ValueError(f"{nome} fora do intervalo [{minimo}, {maximo}]: {valor!r}")
    return v


def risco(lat: float, lon: float, quando: datetime, chuva_mm: float) -> dict:
    """Probabilidade de um atropelamento ser fatal neste local e momento.

    Devolve {"probabilidade_fatal", "nivel" (baixo/medio/alto), "cluster_id", "rank_prioridade", "rank_urbano",
    "motivos"}. cluster_id/rank vêm do ranking oficial (notebook 03) e são None fora de um grupo (> EPS_M).
    Levanta ValueError para entrada inválida.
    """
    lat = _numero("lat", lat, -90, 90)
    lon = _numero("lon", lon, -180, 180)
    chuva = _numero("chuva_mm", chuva_mm, 0, 1_000)
    if not isinstance(quando, datetime):
        raise ValueError(f"quando precisa ser datetime, recebeu {type(quando).__name__}")

    pk = _pacote()
    X = montar_variaveis([lat], [lon], [quando], [chuva], pk["tabelas"])
    prob = float(pk["modelo"].predict_proba(X[pk["variaveis"]])[0, 1])
    cortes = pk["cortes_nivel"]
    nivel = "alto" if prob >= cortes["alto"] else "medio" if prob >= cortes["medio"] else "baixo"

    # grupo oficial (notebook 03): ponto agrupado mais próximo, se a menos de EPS_M
    d, j = pk["oficial_arvore"].query(_rad([lat], [lon]), k=1)
    cluster_id = rank = rank_urbano = None
    if d[0, 0] * R_TERRA <= EPS_M:
        cluster_id = int(pk["oficial_rotulos"][j[0, 0]])
        g = pk["oficial_grupos"][cluster_id]
        rank = int(g["rank_prioridade"])
        rank_urbano = None if pd.isna(g["rank_urbano"]) else int(g["rank_urbano"])

    v = X.iloc[0]
    motivos = []
    if quando.hour < 6:
        motivos.append("madrugada")
    elif quando.hour >= 19:
        motivos.append("noite")
    if v["chovendo"]:
        motivos.append("chuva")
    if v["fim_de_semana"]:
        motivos.append("fim de semana")
    if v["rodovia_local"]:
        motivos.append("rodovia")
    if rank_urbano is not None and rank_urbano <= 20:
        motivos.append("ponto crítico top 20")
    elif cluster_id is not None:
        motivos.append("ponto crítico (DBSCAN)")
    if v["let_local"] > 1.5 * pk["tabelas"]["taxa_global"]:
        motivos.append("local com histórico de mortes")

    return {"probabilidade_fatal": round(prob, 4), "nivel": nivel, "cluster_id": cluster_id,
            "rank_prioridade": rank, "rank_urbano": rank_urbano, "motivos": motivos}
