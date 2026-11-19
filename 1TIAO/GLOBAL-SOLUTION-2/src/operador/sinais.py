"""Sinal simulado do nó ESP32, para demonstrar a Sala de controle sem o Wokwi (plano B).

O tempo extra da travessia vem do cartão (Bilhete Único Idoso/Especial, como o Green Man+ de Singapura) ou da câmera
(quem esqueceu o cartão). Os dois são automáticos, então os sinais não passam por validação manual: a Sala só registra.
"""
from __future__ import annotations

from datetime import datetime

import mensagens as m


def evento_simulado(tipo: str, seq: int, modo: str | None = None) -> dict:
    if tipo not in m.TIPOS_EVENTO:
        raise ValueError(f"tipo de sinal desconhecido: {tipo!r}")
    detalhe = {"simulado": True, **({"modo": modo} if modo else {})}
    return {"v": m.VERSAO, "tipo": tipo, "seq": seq, "boot": "simulado", "detalhe": detalhe,
            "ts": datetime.now(m.FUSO).isoformat(timespec="seconds")}
