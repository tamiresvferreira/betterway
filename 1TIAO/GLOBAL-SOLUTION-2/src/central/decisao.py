"""Decisão do modo do nó (função pura). Spec: docs/specs/2026-11-16-central-design.md §4.

Prioridade (a mesma do nó): ambulância > chuva > escola > pedestre > normal. "Pedestre já na faixa" e o botão de
travessia estendida são decididos no próprio nó (src/esp32/logica.cpp), não aqui.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time

LIMIAR_CHUVA_MM_H = 2.5        # chuva moderada
LIMIAR_ALAGAMENTO_MM_H = 10.0  # chuva forte: "alagamento à frente" (substituto até os pontos de alagamento do CGE)
ETA_AMBULANCIA_S = 60          # a central entra em modo ambulância com chegada em até 60 s (o nó bloqueia o botão a 30 s)
# entrada e saída de escola, dias úteis (cenário: o piloto não tem escola a menos de 300 m)
JANELAS_ESCOLA = ((time(6, 45), time(7, 30)), (time(11, 45), time(13, 15)), (time(17, 45), time(18, 30)))


@dataclass(frozen=True)
class Entradas:
    quando: datetime
    chuva_mm_h: float | None = None      # None = sem dado
    chuva_simulada: bool = False
    pessoas_na_faixa: int = 0            # registros da visão de pessoa na faixa (último minuto, ou do vídeo de demo)
    ambulancia_eta_s: float | None = None
    ambulancia_passou: bool = False


@dataclass(frozen=True)
class Decisao:
    modo: str
    campos: dict = field(default_factory=dict)   # opcionais do comando (mensagens.comando)
    motivo: str = ""


def em_horario_escola(quando: datetime) -> bool:
    if quando.weekday() >= 5:
        return False
    h = quando.time()
    return any(ini <= h <= fim for ini, fim in JANELAS_ESCOLA)


def decidir(e: Entradas) -> Decisao:
    if e.ambulancia_passou:
        return Decisao("ambulancia", {"fim": True}, "ambulância (SIMULADA) passou")
    if e.ambulancia_eta_s is not None and e.ambulancia_eta_s <= ETA_AMBULANCIA_S:
        eta = max(0, round(e.ambulancia_eta_s))
        return Decisao("ambulancia", {"eta_s": eta}, f"ambulância (SIMULADA) a {eta} s")
    if e.chuva_mm_h is not None and e.chuva_mm_h >= LIMIAR_CHUVA_MM_H:
        forte = e.chuva_mm_h >= LIMIAR_ALAGAMENTO_MM_H
        origem = " (SIMULADA)" if e.chuva_simulada else " (previsão Open-Meteo)"
        return Decisao("chuva", {"alagamento": forte},
                       f"chuva {e.chuva_mm_h:.1f} mm/h{origem}" + (" · risco de alagamento" if forte else ""))
    if em_horario_escola(e.quando):
        return Decisao("escola", {}, f"horário de entrada/saída de escola ({e.quando:%H:%M}, cenário)")
    if e.pessoas_na_faixa > 0:
        return Decisao("pedestre", {"faixa_ocupada": True}, f"visão: {e.pessoas_na_faixa} registros de pessoa na faixa")
    return Decisao("normal", {}, "sem chuva, fora do horário de escola, sem pedestre nem ambulância")
