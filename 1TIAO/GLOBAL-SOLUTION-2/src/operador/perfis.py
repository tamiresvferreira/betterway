"""Perfis da interface do operador BetterWay e o que cada um pode fazer (spec 2026-11-17 §2, §4a).

A permissão é conferida aqui, no servidor, antes de gravar ou publicar — esconder o botão na tela não basta.
"""
from __future__ import annotations

PERFIS = {"transito": "Trânsito", "saude": "Saúde", "gestao": "Gestão"}
ACOES = ("confirmar", "descartar", "reportar", "cenario", "despachar", "encerrar", "convidar", "registrar")
_PERMISSOES = {
    "transito": {"confirmar", "descartar", "reportar", "cenario", "registrar"},
    "saude": {"despachar", "encerrar", "registrar"},
    "gestao": {"convidar", "registrar"},     # lê tudo, convida a equipe e registra pela câmera
}


def pode(perfil: str | None, acao: str) -> bool:
    return acao in _PERMISSOES.get(perfil or "", set())


class SemPermissao(PermissionError):
    """O perfil da sessão não pode fazer esta ação."""


def exigir(perfil: str | None, acao: str) -> None:
    if not pode(perfil, acao):
        raise SemPermissao(f"o perfil {perfil!r} não pode {acao!r}")
