"""Despacho da ambulância SIMULADA (spec 2026-11-17 §5): quando a Saúde despacha, o nó recebe a aproximação.

A ambulância parte a 600 m e vem a 40 km/h (54 s), como no cenário da central: `eta_s` a cada 10 s e um `fim`.
Não há integração com o SAMU — o despacho é uma simulação, e o comando é o mesmo contrato de mensagens.py.
"""
from __future__ import annotations

from datetime import datetime

import mensagens as m
from fontes import eta_ambulancia

DIST_M, VEL_KMH = 600, 40
DURACAO_S = DIST_M / (VEL_KMH / 3.6)
REENVIO_S = 10
JANELA_FIM_S = 30           # depois disso um despacho é velho demais para mandar o "fim" (ex.: servidor reiniciado)


def comando_despacho(t_s: float) -> dict | None:
    """Comando para `t_s` segundos depois do despacho; None quando não há mais nada a mandar."""
    if t_s < DURACAO_S:
        return m.comando("ambulancia", eta_s=round(eta_ambulancia(t_s, DIST_M, VEL_KMH)))
    if t_s < DURACAO_S + JANELA_FIM_S:
        return m.comando("ambulancia", fim=True)
    return None


class Despachante:
    """Decide o que publicar a cada passo, para cada despacho em andamento (um por servidor)."""

    def __init__(self, publicar):
        self.publicar = publicar
        self._ultimo: dict[int, float] = {}      # ocorrência → t do último eta enviado
        self._fim: set[int] = set()

    def passo(self, despachadas: list[tuple[int, float]]) -> None:
        for oc_id, t in despachadas:
            if oc_id in self._fim:
                continue
            cmd = comando_despacho(t)
            if cmd is None:
                continue
            if cmd.get("fim"):
                if oc_id in self._ultimo and self.publicar(cmd):   # só fecha o que este servidor abriu
                    self._fim.add(oc_id)
            elif t - self._ultimo.get(oc_id, -1e9) >= REENVIO_S and self.publicar(cmd):
                self._ultimo[oc_id] = t


def despachadas_recentes(con, agora: datetime, janela_s: float = DURACAO_S + JANELA_FIM_S) -> list[tuple[int, float]]:
    """(ocorrência, segundos desde o despacho) das que foram despachadas há menos de `janela_s`."""
    saida = []
    for oc_id, ts in con.execute("SELECT h.ocorrencia_id, h.timestamp FROM ocorrencias_historico h "
                                 "JOIN ocorrencias o ON o.id = h.ocorrencia_id "
                                 "WHERE h.acao = 'despachar' AND o.estado = 'despachada'"):
        t = (agora - datetime.fromisoformat(ts)).total_seconds()
        if 0 <= t < janela_s:
            saida.append((oc_id, t))
    return saida
