"""Leituras de cartão na faixa (Bilhete Único Idoso ou Especial, como o Green Man+ de Singapura).

Cada leitura pede mais tempo para atravessar. Fica registrado só o tipo de cartão, a faixa, o horário e o tempo extra:
nenhum número de cartão nem nome (LGPD). A câmera também pede tempo para quem esqueceu o cartão; essas entram com
origem "camera".
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

TIPOS = {"idoso": "Bilhete Único Idoso", "especial": "Bilhete Único Especial (pessoa com deficiência)"}
ORIGENS = {"cartao": "Cartão", "camera": "Câmera"}
COMPRIMENTO_M, VEL_NORMAL, VEL_ESTENDIDA = 10.0, 1.2, 0.8      # os mesmos do nó ESP32

SCHEMA = """
CREATE TABLE IF NOT EXISTS leituras_cartao (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT NOT NULL,
    origem     TEXT NOT NULL CHECK (origem IN ('cartao', 'camera')),
    tipo       TEXT,
    faixa      TEXT NOT NULL,
    tempo_s    REAL NOT NULL,
    extra_s    REAL NOT NULL,
    simulado   INTEGER NOT NULL DEFAULT 0 CHECK (simulado IN (0, 1))
);
"""


def migrar(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)


def tempos(comprimento_m: float = COMPRIMENTO_M) -> tuple[float, float]:
    """(verde normal, verde estendido) em segundos, como o nó calcula: comprimento ÷ velocidade."""
    return comprimento_m / VEL_NORMAL, comprimento_m / VEL_ESTENDIDA


def registrar(con, *, origem: str, tipo: str | None = None, faixa: str = "Largo da Concórdia", simulado: bool = False,
              agora: datetime | None = None) -> dict:
    if origem not in ORIGENS:
        raise ValueError(f"origem desconhecida: {origem!r}")
    if origem == "cartao" and tipo not in TIPOS:
        raise ValueError("cartão sem tipo válido")
    if origem == "camera":
        tipo = None
    from mensagens import FUSO
    normal, estendido = tempos()
    ts = (agora or datetime.now(FUSO)).isoformat(timespec="seconds")
    with con:
        cur = con.execute("INSERT INTO leituras_cartao (timestamp, origem, tipo, faixa, tempo_s, extra_s, simulado) "
                          "VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (ts, origem, tipo, faixa, round(estendido, 1), round(estendido - normal, 1), int(simulado)))
    return {"id": cur.lastrowid, "timestamp": ts, "origem": origem, "tipo": tipo, "faixa": faixa,
            "tempo_s": round(estendido, 1), "extra_s": round(estendido - normal, 1), "simulado": simulado}


def recentes(con, limite: int = 20) -> list[dict]:
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute("SELECT * FROM leituras_cartao ORDER BY id DESC LIMIT ?", (limite,))]
    finally:
        con.row_factory = None


def mensagem_sms(via: str, distancia_m: int = 1000) -> str:
    """Texto do alerta aos motoristas à frente da ambulância (cell broadcast, sem saber número nem identidade)."""
    return (f"Alerta BetterWay: ambulância a {distancia_m / 1000:.0f} km atrás de você na {via}. "
            "Abra caminho com segurança, sem avançar o sinal.").replace(".0 km", " km")
