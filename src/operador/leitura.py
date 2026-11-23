"""Leitura da situação de um ponto crítico: junta as evidências (histórico, chuva, câmera, modelo) e conclui.

Cada evidência diz o que viu e de onde veio. A conclusão nunca sai de uma evidência sozinha:
- histórico que se repete + câmera vendo conflito ou pessoa com mobilidade reduzida + (chuva ou risco acima do normal
  do ponto) → padrão;
- histórico + mais uma evidência, ou câmera + risco acima do normal → atenção;
- o resto → normal.
Cada mudança de conclusão vai para a tabela `leituras` (a linha do tempo do Painel).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from padrao import Padrao

CHUVA_FORTE_MM_H = 2.5            # a mesma chuva moderada que muda o modo do nó (central/decisao.py)
RISCO_ACIMA = 1.25               # o risco de agora pesa quando passa de 1,25× a média do próprio ponto


@dataclass(frozen=True)
class Camera:
    pessoas_na_faixa: int
    conflitos: int
    mobilidade_reduzida: int
    fonte: str                     # "ao vivo" ou "demo" (vídeo de referência)


@dataclass(frozen=True)
class Evidencia:
    nome: str
    texto: str
    fonte: str
    estado: str                    # "pesa" | "nao_pesa" | "sem_dado"


@dataclass(frozen=True)
class Leitura:
    nivel: str                     # "padrao" | "atencao" | "normal"
    titulo: str
    recomendacao: str
    evidencias: list = field(default_factory=list)


TITULOS = {"padrao": "Situação parecida com a dos atropelamentos já registrados aqui",
           "atencao": "Atenção: há sinais de risco na travessia",
           "normal": "Sem sinais de risco fora do comum"}
RECOMENDACOES = {
    "padrao": "Reforçar a proteção da travessia agora: tempo estendido para quem atravessa e alerta aos motoristas.",
    "atencao": "Acompanhar a câmera e deixar a equipe de trânsito avisada.",
    "normal": "Nenhuma ação necessária. A leitura é refeita a cada minuto.",
}


def _n(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def ler(padrao: Padrao, camera: Camera | None, chuva_mm_h: float | None, risco_vezes_local: float | None,
        risco_vezes_cidade: float | None = None) -> Leitura:
    """`risco_vezes_local`: risco de agora ÷ média do próprio ponto ao longo do dia (modelo do notebook 06);
    `risco_vezes_cidade`: risco de agora ÷ média da cidade (só para o texto)."""
    hist = Evidencia("Histórico", padrao.texto, "Infosiga-SP", "pesa" if padrao.se_repete else "nao_pesa")
    if chuva_mm_h is None:
        clima = Evidencia("Chuva agora", "Previsão de chuva indisponível no momento.", "Open-Meteo", "sem_dado")
    else:
        forte = chuva_mm_h >= CHUVA_FORTE_MM_H
        clima = Evidencia("Chuva agora", f"{_n(chuva_mm_h)} mm/h" + (", chuva moderada ou forte" if forte else ""),
                          "Open-Meteo", "pesa" if forte else "nao_pesa")
    if camera is None:
        cam = Evidencia("Câmera", "Sem leitura da câmera.", "Visão computacional", "sem_dado")
    else:
        partes = [f"{camera.pessoas_na_faixa} pessoas na faixa",
                  f"{camera.conflitos} {'conflito' if camera.conflitos == 1 else 'conflitos'} com veículo",
                  f"{camera.mobilidade_reduzida} com mobilidade reduzida"]
        origem = "vídeo de referência" if camera.fonte == "demo" else "últimos 10 min"
        cam = Evidencia("Câmera", f"{', '.join(partes)} ({origem})", "Visão computacional",
                        "pesa" if camera.conflitos or camera.mobilidade_reduzida else "nao_pesa")
    if risco_vezes_local is None:
        mod = Evidencia("Modelo", "Modelo de risco indisponível.", "Modelo de risco", "sem_dado")
    else:
        acima = risco_vezes_local >= RISCO_ACIMA
        txt = f"Risco agora: {_n(risco_vezes_local)}× a média deste ponto"
        if risco_vezes_cidade is not None:
            txt += f" e {_n(risco_vezes_cidade)}× a média da cidade"
        mod = Evidencia("Modelo", txt, "Modelo de risco", "pesa" if acima else "nao_pesa")
    h, c, cl, m = (e.estado == "pesa" for e in (hist, cam, clima, mod))
    if h and c and (cl or m):
        nivel = "padrao"
    elif (h and (c or cl or m)) or (c and m):
        nivel = "atencao"
    else:
        nivel = "normal"
    return Leitura(nivel, TITULOS[nivel], RECOMENDACOES[nivel], [hist, clima, cam, mod])


# ---------------------------------------------------------------- linha do tempo
SCHEMA = """
CREATE TABLE IF NOT EXISTS leituras (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    nivel     TEXT NOT NULL,
    resumo    TEXT NOT NULL,
    simulado  INTEGER NOT NULL DEFAULT 0
);
"""


def migrar(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)


def registrar(con, leitura: Leitura, quando: datetime, simulado: bool) -> bool:
    """Grava só quando a conclusão muda em relação à última leitura do mesmo tipo (real ou simulada)."""
    ultima = con.execute("SELECT nivel FROM leituras WHERE simulado = ? ORDER BY id DESC LIMIT 1",
                         (int(simulado),)).fetchone()
    if ultima and ultima[0] == leitura.nivel:
        return False
    resumo = " · ".join(f"{e.nome}: {e.texto}" for e in leitura.evidencias if e.estado == "pesa") or "nenhuma evidência"
    with con:
        con.execute("INSERT INTO leituras (timestamp, nivel, resumo, simulado) VALUES (?, ?, ?, ?)",
                    (quando.isoformat(timespec="seconds"), leitura.nivel, resumo, int(simulado)))
    return True


def historico(con, limite: int = 20) -> list[dict]:
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute("SELECT * FROM leituras ORDER BY id DESC LIMIT ?", (limite,))]
    finally:
        con.row_factory = None
