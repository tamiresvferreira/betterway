"""Registro manual de ocorrência a partir de uma câmera (relatório do operador).

Quem acompanha uma câmera descreve o que viu, aciona ambulância, central de trânsito ou polícia (simulados) e anexa
quadros do vídeo (print com o horário da captura). Qualquer perfil pode registrar. O relatório nasce como rascunho
(quem registrou e quando) e é enviado depois (quem enviou e quando). Com a ambulância acionada, o envio abre uma
ocorrência já confirmada, que aparece para a Saúde em Atendimentos.

Os quadros vêm dos vídeos já anotados e com rostos e placas borrados; ficam em `data/processed/registros/`, fora do Git.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from perfis import exigir

PASTA_QUADROS = Path(__file__).resolve().parents[2] / "data" / "processed" / "registros"
SITUACOES = {"acidente": "Acidente ou atropelamento", "pessoa_ajuda": "Pessoa precisando de ajuda",
             "veiculo_parado": "Veículo parado ou quebrado", "conflito": "Conflito ou risco na faixa",
             "outro": "Outra situação"}
ACIONAMENTOS = {"ambulancia": "Ambulância (SAMU)", "transito": "Central de trânsito (CET)", "policia": "Polícia"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS registros (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    camera         TEXT NOT NULL,
    local          TEXT NOT NULL,
    cluster_id     INTEGER,
    video_id       TEXT,
    situacao       TEXT,
    descricao      TEXT,
    acionamentos   TEXT,
    registrado_por TEXT NOT NULL,
    registrado_em  TEXT NOT NULL,
    enviado_por    TEXT,
    enviado_em     TEXT,
    ocorrencia_id  INTEGER
);
CREATE TABLE IF NOT EXISTS registros_quadros (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    registro_id   INTEGER NOT NULL REFERENCES registros(id),
    segundo       REAL NOT NULL,
    capturado_em  TEXT NOT NULL,
    capturado_por TEXT NOT NULL,
    arquivo       TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Quadro:
    id: int
    segundo: float
    capturado_em: str
    capturado_por: str
    arquivo: Path


def migrar(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)


def _agora(agora: datetime | None) -> str:
    from mensagens import FUSO
    return (agora or datetime.now(FUSO)).isoformat(timespec="seconds")


def iniciar(con, *, usuario, camera: str, local: str, cluster_id: int | None = None, video_id: str | None = None,
            agora: datetime | None = None) -> int:
    """Abre o rascunho do relatório (quem registrou e quando)."""
    exigir(getattr(usuario, "perfil", None), "registrar")
    with con:
        cur = con.execute("INSERT INTO registros (camera, local, cluster_id, video_id, registrado_por, registrado_em) "
                          "VALUES (?, ?, ?, ?, ?, ?)", (camera, local, cluster_id, video_id, usuario.usuario,
                                                        _agora(agora)))
    return cur.lastrowid


def quadro_do_video(video: Path, segundo: float):
    """Imagem (BGR, numpy) do vídeo no segundo pedido, ou None se não der para ler."""
    import cv2
    cap = cv2.VideoCapture(str(video))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, segundo) * 1000)
        ok, img = cap.read()
        return img if ok else None
    finally:
        cap.release()


def duracao_s(video: Path) -> float:
    import cv2
    cap = cv2.VideoCapture(str(video))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        return n / fps if fps else 0.0
    finally:
        cap.release()


def capturar(con, registro_id: int, *, usuario, video: Path, segundo: float, pasta: Path = PASTA_QUADROS,
             agora: datetime | None = None) -> Quadro:
    """Tira o print do vídeo no segundo escolhido, grava o PNG com o horário no nome e anexa ao relatório."""
    import cv2
    exigir(getattr(usuario, "perfil", None), "registrar")
    r = _registro(con, registro_id)
    if r is None:
        raise ValueError(f"registro {registro_id} não existe")
    if r["enviado_em"]:
        raise ValueError("este relatório já foi enviado")
    img = quadro_do_video(video, segundo)
    if img is None:
        raise ValueError("não foi possível ler esse momento do vídeo")
    ts = _agora(agora)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"registro_{registro_id:04d}_{ts[:19].replace(':', '').replace('-', '')}_{segundo:06.2f}s.png"
    cv2.imwrite(str(arq), img)
    with con:
        cur = con.execute("INSERT INTO registros_quadros (registro_id, segundo, capturado_em, capturado_por, arquivo) "
                          "VALUES (?, ?, ?, ?, ?)", (registro_id, float(segundo), ts, usuario.usuario, str(arq)))
    return Quadro(cur.lastrowid, float(segundo), ts, usuario.usuario, arq)


def remover_quadro(con, quadro_id: int) -> None:
    with con:
        linha = con.execute("SELECT q.arquivo, r.enviado_em FROM registros_quadros q JOIN registros r "
                            "ON r.id = q.registro_id WHERE q.id = ?", (quadro_id,)).fetchone()
        if linha is None or linha[1]:
            return
        con.execute("DELETE FROM registros_quadros WHERE id = ?", (quadro_id,))
    Path(linha[0]).unlink(missing_ok=True)


def quadros(con, registro_id: int) -> list[Quadro]:
    return [Quadro(i, s, em, por, Path(a)) for i, s, em, por, a in con.execute(
        "SELECT id, segundo, capturado_em, capturado_por, arquivo FROM registros_quadros WHERE registro_id = ? "
        "ORDER BY id", (registro_id,))]


def enviar(con, registro_id: int, *, usuario, situacao: str, descricao: str, acionamentos: list[str],
           agora: datetime | None = None) -> int | None:
    """Fecha o relatório (quem enviou e quando). Com ambulância, abre uma ocorrência confirmada para a Saúde e
    devolve o número dela."""
    exigir(getattr(usuario, "perfil", None), "registrar")
    if situacao not in SITUACOES:
        raise ValueError("escolha o tipo de situação")
    if not (descricao or "").strip():
        raise ValueError("descreva o que você viu")
    desconhecidos = set(acionamentos) - set(ACIONAMENTOS)
    if desconhecidos:
        raise ValueError(f"acionamento desconhecido: {sorted(desconhecidos)}")
    r = _registro(con, registro_id)
    if r is None:
        raise ValueError(f"registro {registro_id} não existe")
    if r["enviado_em"]:
        raise ValueError("este relatório já foi enviado")
    ts = _agora(agora)
    oc_id = None
    with con:
        if "ambulancia" in acionamentos:
            cur = con.execute("INSERT INTO ocorrencias (cluster_id, origem, tipo, video_id, segundo, estado, aberta_em) "
                              "VALUES (?, 'operador', 'registro_camera', ?, NULL, 'confirmada', ?)",
                              (r["cluster_id"] or 0, r["video_id"], ts))
            oc_id = cur.lastrowid
            con.execute("INSERT INTO ocorrencias_historico (ocorrencia_id, timestamp, acao, de, para, usuario, motivo) "
                        "VALUES (?, ?, 'registrar', NULL, 'confirmada', ?, ?)",
                        (oc_id, ts, usuario.usuario, f"Relatório Nº {registro_id} ({r['camera']})"))
        n = con.execute("UPDATE registros SET situacao = ?, descricao = ?, acionamentos = ?, enviado_por = ?, "
                        "enviado_em = ?, ocorrencia_id = ? WHERE id = ? AND enviado_em IS NULL",
                        (situacao, descricao.strip(), ",".join(a for a in ACIONAMENTOS if a in acionamentos),
                         usuario.usuario, ts, oc_id, registro_id)).rowcount
        if n != 1:
            raise ValueError("este relatório já foi enviado")
    return oc_id


def _registro(con, registro_id: int) -> dict | None:
    con.row_factory = sqlite3.Row
    try:
        r = con.execute("SELECT * FROM registros WHERE id = ?", (registro_id,)).fetchone()
    finally:
        con.row_factory = None
    return dict(r) if r else None


def obter(con, registro_id: int) -> dict | None:
    return _registro(con, registro_id)


def enviados(con, limite: int = 20) -> list[dict]:
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute("SELECT * FROM registros WHERE enviado_em IS NOT NULL "
                                             "ORDER BY enviado_em DESC, id DESC LIMIT ?", (limite,))]
    finally:
        con.row_factory = None


def do_ocorrencia(con, oc_id: int) -> dict | None:
    """O relatório que abriu esta ocorrência (para mostrar câmera e local na Saúde)."""
    linha = con.execute("SELECT id FROM registros WHERE ocorrencia_id = ?", (oc_id,)).fetchone()
    return _registro(con, linha[0]) if linha else None
