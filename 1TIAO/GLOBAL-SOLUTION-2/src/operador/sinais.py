"""Validação dos sinais que o nó ESP32 relata na Sala de controle.

Trânsito e Saúde olham o sinal (ex.: botão de travessia apertado, verde estendido) e confirmam que é real ou contestam
com um motivo. Fica gravado quem validou, de que área e quando. Cada sinal é identificado por (boot, seq), como o nó
publica, e é validado uma vez. Gestão acompanha.

Para demonstrar sem o ESP32 (Wokwi fora do ar ou sem rede), `evento_simulado` monta o mesmo evento que o nó publicaria,
marcado como simulado.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

import mensagens as m
from perfis import PERFIS, exigir

DECISOES = {"confirmado": "Confirmado", "contestado": "Contestado"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS validacoes_sinais (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    boot        TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    tipo        TEXT NOT NULL,
    recebido_em TEXT,
    decisao     TEXT NOT NULL CHECK (decisao IN ('confirmado', 'contestado')),
    usuario     TEXT NOT NULL,
    area        TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    nota        TEXT,
    UNIQUE (boot, seq)
);
"""


def migrar(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)


def validar(con, evento: dict, *, usuario, decisao: str, nota: str | None = None,
            agora: datetime | None = None) -> None:
    perfil = getattr(usuario, "perfil", None)
    exigir(perfil, "validar_sinal")
    if decisao not in DECISOES:
        raise ValueError(f"decisão desconhecida: {decisao!r}")
    nota = (nota or "").strip() or None
    if decisao == "contestado" and not nota:
        raise ValueError("contestar exige um motivo")
    ts = (agora or datetime.now(m.FUSO)).isoformat(timespec="seconds")
    try:
        with con:
            con.execute("INSERT INTO validacoes_sinais (boot, seq, tipo, recebido_em, decisao, usuario, area, "
                        "timestamp, nota) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(evento["boot"]), int(evento["seq"]), evento["tipo"], evento.get("recebido_em"), decisao,
                         usuario.usuario, PERFIS[perfil], ts, nota))
    except sqlite3.IntegrityError:
        raise ValueError("este sinal já foi validado") from None


def validacoes(con) -> dict[tuple[str, int], dict]:
    con.row_factory = sqlite3.Row
    try:
        return {(r["boot"], r["seq"]): dict(r) for r in con.execute("SELECT * FROM validacoes_sinais")}
    finally:
        con.row_factory = None


def evento_simulado(tipo: str, seq: int, modo: str | None = None) -> dict:
    if tipo not in m.TIPOS_EVENTO:
        raise ValueError(f"tipo de sinal desconhecido: {tipo!r}")
    detalhe = {"simulado": True, **({"modo": modo} if modo else {})}
    return {"v": m.VERSAO, "tipo": tipo, "seq": seq, "boot": "simulado", "detalhe": detalhe,
            "ts": datetime.now(m.FUSO).isoformat(timespec="seconds")}
