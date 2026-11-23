"""Ocorrências da interface do operador BetterWay (spec 2026-11-17 §5).

pendente ──Trânsito confirma──▶ confirmada ──Saúde despacha──▶ despachada ──Saúde encerra──▶ encerrada
    └────Trânsito descarta───▶ descartada (com motivo)

Nenhuma imagem é guardada: só o identificador do clipe e o segundo do evento. Cada mudança grava quem e quando.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from perfis import exigir

CLUSTER_PILOTO = 139
TRANSICOES = {               # ação → (de, para)
    "confirmar": ("pendente", "confirmada"),
    "descartar": ("pendente", "descartada"),
    "despachar": ("confirmada", "despachada"),
    "encerrar": ("despachada", "encerrada"),
}
ESTADOS = ("pendente", "confirmada", "descartada", "despachada", "encerrada")
TIPOS = {"suspeita_acidente": "Suspeita de acidente", "ocorrencia_reportada": "Ocorrência reportada",
         "registro_camera": "Registro pela câmera"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS ocorrencias (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_id INTEGER NOT NULL,
    origem     TEXT NOT NULL CHECK (origem IN ('visao', 'operador')),
    tipo       TEXT NOT NULL,
    video_id   TEXT,
    segundo    REAL,
    estado     TEXT NOT NULL DEFAULT 'pendente',
    aberta_em  TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ocorrencias_visao_unica ON ocorrencias (video_id, tipo, segundo)
    WHERE origem = 'visao';
CREATE TABLE IF NOT EXISTS ocorrencias_historico (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ocorrencia_id INTEGER NOT NULL REFERENCES ocorrencias(id),
    timestamp     TEXT NOT NULL,
    acao          TEXT NOT NULL,
    de            TEXT,
    para          TEXT NOT NULL,
    usuario       TEXT NOT NULL,
    motivo        TEXT
);
"""


class TransicaoInvalida(ValueError):
    """A ocorrência não está no estado em que esta ação é possível."""


def migrar(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)


def _agora(agora: datetime | None) -> str:
    from mensagens import FUSO
    return (agora or datetime.now(FUSO)).isoformat(timespec="seconds")


def proximo_estado(estado: str, acao: str) -> str:
    if acao not in TRANSICOES:
        raise TransicaoInvalida(f"ação desconhecida: {acao!r}")
    de, para = TRANSICOES[acao]
    if estado != de:
        raise TransicaoInvalida(f"não dá para {acao} uma ocorrência {estado}")
    return para


def abrir(con, *, origem: str, tipo: str, usuario=None, cluster_id: int = CLUSTER_PILOTO, video_id: str | None = None,
          segundo: float | None = None, agora: datetime | None = None) -> int:
    """Abre uma ocorrência pendente. Pela visão é idempotente (mesmo clipe, tipo e segundo → mesma ocorrência)."""
    if origem == "operador":
        exigir(getattr(usuario, "perfil", None), "reportar")
        quem = usuario.usuario
    elif origem == "visao":
        quem = "visao"
        ja = con.execute("SELECT id FROM ocorrencias WHERE origem = 'visao' AND video_id IS ? AND tipo = ? "
                         "AND segundo IS ?", (video_id, tipo, segundo)).fetchone()
        if ja:
            return ja[0]
    else:
        raise ValueError(f"origem inválida: {origem!r}")
    ts = _agora(agora)
    with con:
        cur = con.execute("INSERT INTO ocorrencias (cluster_id, origem, tipo, video_id, segundo, aberta_em) "
                          "VALUES (?, ?, ?, ?, ?, ?)", (cluster_id, origem, tipo, video_id, segundo, ts))
        con.execute("INSERT INTO ocorrencias_historico (ocorrencia_id, timestamp, acao, de, para, usuario) "
                    "VALUES (?, ?, 'abrir', NULL, 'pendente', ?)", (cur.lastrowid, ts, quem))
    return cur.lastrowid


def obter(con, oc_id: int) -> dict | None:
    con.row_factory = sqlite3.Row
    try:
        r = con.execute("SELECT * FROM ocorrencias WHERE id = ?", (oc_id,)).fetchone()
    finally:
        con.row_factory = None
    return dict(r) if r else None


def aplicar(con, oc_id: int, acao: str, usuario, motivo: str | None = None, agora: datetime | None = None) -> str:
    """Aplica a ação conferindo o perfil e o estado; devolve o novo estado."""
    exigir(getattr(usuario, "perfil", None), acao)
    if acao == "descartar" and not (motivo or "").strip():
        raise ValueError("descartar exige um motivo")
    atual = obter(con, oc_id)
    if atual is None:
        raise TransicaoInvalida(f"ocorrência {oc_id} não existe")
    para = proximo_estado(atual["estado"], acao)
    with con:
        n = con.execute("UPDATE ocorrencias SET estado = ? WHERE id = ? AND estado = ?",
                        (para, oc_id, atual["estado"])).rowcount
        if n != 1:                       # outra sessão mudou antes
            raise TransicaoInvalida(f"a ocorrência {oc_id} mudou enquanto isso; atualize a tela")
        con.execute("INSERT INTO ocorrencias_historico (ocorrencia_id, timestamp, acao, de, para, usuario, motivo) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (oc_id, _agora(agora), acao, atual["estado"], para, usuario.usuario, (motivo or "").strip() or None))
    return para


def listar(con, estados=None) -> list[dict]:
    sql, params = "SELECT * FROM ocorrencias", ()
    if estados:
        sql += f" WHERE estado IN ({','.join('?' * len(estados))})"
        params = tuple(estados)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql + " ORDER BY id DESC", params)]
    finally:
        con.row_factory = None


def tempos(con, oc_id: int) -> dict[str, dict]:
    """Estado → {timestamp, usuario, motivo}, na ordem em que aconteceram."""
    return {para: {"timestamp": ts, "usuario": u, "motivo": mo} for para, ts, u, mo in con.execute(
        "SELECT para, timestamp, usuario, motivo FROM ocorrencias_historico WHERE ocorrencia_id = ? ORDER BY id",
        (oc_id,))}
