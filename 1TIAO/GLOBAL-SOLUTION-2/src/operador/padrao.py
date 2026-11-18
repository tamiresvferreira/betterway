"""Padrão que se repete: a situação de agora parece com a dos atropelamentos que já aconteceram no local?

Compara o agora (tipo de dia, hora ±1 h e, se chove, a chuva) com o histórico do grupo no Infosiga-SP. Só chama de
"padrão se repetindo" quando a janela tem casos suficientes e concentra bem mais atropelamentos do que uma janela
qualquer de 3 horas. Explica o risco; o número de risco continua vindo do modelo (notebook 06, `risco()`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

MIN_CASOS = 3          # menos que isso é coincidência, não padrão
MIN_VEZES = 1.5        # a janela concentra pelo menos 1,5× o esperado se os casos fossem espalhados
CHUVA_MM_H = 0.5       # chuva "agora" e chuva registrada no atropelamento


@dataclass(frozen=True)
class Padrao:
    total: int
    casos_na_janela: int
    casos_com_chuva: int | None     # só quando chove agora
    vezes_a_media: float
    se_repete: bool
    texto: str


def _n(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def padrao_agora(historico: pd.DataFrame, quando: datetime, chuva_mm_h: float | None = None) -> Padrao:
    """`historico`: colunas data_sinistro, hora e chuva_mm (tabela `sinistros` de um grupo)."""
    total = len(historico)
    util = quando.weekday() < 5
    tipo = "dia útil" if util else "fim de semana"
    horas = {(quando.hour + d) % 24 for d in (-1, 0, 1)}
    ini, fim = (quando.hour - 1) % 24, (quando.hour + 1) % 24
    if total == 0:
        return Padrao(0, 0, None, 0.0, False, "Sem atropelamentos registrados neste local no Infosiga-SP (2022–2025).")
    dias = pd.to_datetime(historico["data_sinistro"]).dt.day_of_week
    mesmo_dia = (dias < 5) if util else (dias >= 5)
    janela = historico[mesmo_dia.to_numpy() & historico["hora"].isin(horas).to_numpy()]
    n = len(janela)
    esperado = total * (3 / 24) * ((5 if util else 2) / 7)
    vezes = n / esperado if esperado else 0.0
    chovendo = chuva_mm_h is not None and chuva_mm_h >= CHUVA_MM_H
    com_chuva = int((janela["chuva_mm"].fillna(0) >= CHUVA_MM_H).sum()) if chovendo else None
    se_repete = n >= MIN_CASOS and vezes >= MIN_VEZES
    base = f"{n} dos {total} atropelamentos aqui {'foi' if n == 1 else 'foram'} em {tipo}, entre {ini}h e {fim}h"
    if chovendo:
        base += f", {com_chuva or 'nenhum'} com chuva"
    if se_repete:
        texto = f"{base} — {_n(vezes)} vezes o esperado para uma janela de 3 horas."
    elif n:
        texto = f"{base} — não chega a ser um padrão."
    else:
        texto = f"Nenhum atropelamento registrado aqui em {tipo} entre {ini}h e {fim}h."
    return Padrao(total, n, com_chuva, round(vezes, 2), se_repete, texto)
