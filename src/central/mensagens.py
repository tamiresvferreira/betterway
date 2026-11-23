"""Contrato MQTT entre a central (ou o roteiro) e o nó ESP32 da faixa.

Ver docs/specs/2026-11-13-no-esp32-design.md §6. O mesmo contrato é validado no firmware (src/esp32/sketch.ino).
As mensagens não carregam nenhum dado pessoal: só modo, fase e contagens.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
NO_ID = "largo-concordia"
PREFIXO = f"viasegura/gs2026/no/{NO_ID}/"
TOPICO_COMANDO = PREFIXO + "comando"
TOPICO_ESTADO = PREFIXO + "estado"
TOPICO_EVENTO = PREFIXO + "evento"

VERSAO = 1
MODOS = ("normal", "pedestre", "escola", "chuva", "ambulancia")
# campo opcional → modo em que ele é permitido
OPCIONAIS = {"faixa_ocupada": "pedestre", "estendida": "pedestre", "alagamento": "chuva", "eta_s": "ambulancia",
             "fim": "ambulancia"}
TIPOS_EVENTO = frozenset({
    "cartao_lido", "camera_pediu_tempo", "travessia_estendida", "pedido_recusado_ambulancia",
    "pedido_atendido_apos_ambulancia",
    "modo_alterado", "sem_central_volta_normal", "comando_invalido",
})


class ComandoInvalido(ValueError):
    """Comando que o nó recusaria (ele ignoraria e publicaria `comando_invalido`)."""


def _numero_valido(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0


def validar_comando(d) -> list[str]:
    """Lista de erros do comando (vazia = válido)."""
    if not isinstance(d, dict):
        return ["comando não é um objeto JSON"]
    erros = []
    if d.get("v") != VERSAO:
        erros.append(f"v deve ser {VERSAO}")
    for campo in ("id", "ts"):
        if not isinstance(d.get(campo), str) or not d.get(campo):
            erros.append(f"{campo} ausente")
    modo = d.get("modo")
    if modo not in MODOS:
        erros.append(f"modo desconhecido: {modo!r}")
    for campo, modo_do_campo in OPCIONAIS.items():
        if campo not in d:
            continue
        if modo != modo_do_campo:
            erros.append(f"{campo} só vale no modo {modo_do_campo}")
        elif campo == "eta_s":
            if not _numero_valido(d[campo]):
                erros.append("eta_s deve ser número finito ≥ 0")
        elif not isinstance(d[campo], bool):
            erros.append(f"{campo} deve ser verdadeiro/falso")
    if modo == "ambulancia" and not d.get("fim") and "eta_s" not in d:
        erros.append("ambulância sem fim precisa de eta_s (tempo de chegada)")
    extras = set(d) - {"v", "id", "ts", "modo", *OPCIONAIS}
    if extras:
        erros.append(f"campos desconhecidos: {sorted(extras)}")
    return erros


def comando(modo: str, *, ts: datetime | None = None, id: str | None = None, **opcionais) -> dict:
    """Comando pronto para publicar em TOPICO_COMANDO; levanta ComandoInvalido se o nó fosse recusá-lo."""
    d = {"v": VERSAO, "id": id or uuid.uuid4().hex[:12], "modo": modo,
         "ts": (ts or datetime.now(FUSO)).isoformat(timespec="seconds"), **opcionais}
    erros = validar_comando(d)
    if erros:
        raise ComandoInvalido("; ".join(erros))
    return d


def validar_evento(d) -> list[str]:
    """Lista de erros de um evento publicado pelo nó em TOPICO_EVENTO (vazia = válido)."""
    if not isinstance(d, dict):
        return ["evento não é um objeto JSON"]
    erros = []
    if d.get("v") != VERSAO:
        erros.append(f"v deve ser {VERSAO}")
    if d.get("tipo") not in TIPOS_EVENTO:
        erros.append(f"tipo desconhecido: {d.get('tipo')!r}")
    seq = d.get("seq")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        erros.append("seq deve ser inteiro ≥ 0")
    if not isinstance(d.get("boot"), str) or not d.get("boot"):
        erros.append("boot ausente")
    if "detalhe" in d and not isinstance(d["detalhe"], dict):
        erros.append("detalhe deve ser objeto")
    return erros
