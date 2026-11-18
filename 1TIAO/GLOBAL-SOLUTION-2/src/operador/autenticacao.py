"""Autenticação da interface do operador BetterWay (spec 2026-11-17 §4a).

Senha com scrypt e sal por usuário, comparação em tempo constante, bloqueio após 5 erros, sessão de 30 min.
A senha nunca é gravada nem registrada. Usuários são criados só por este CLI:

    python src/operador/autenticacao.py criar <usuario> <perfil> "<nome exibido>"     # pede a senha sem eco
    python src/operador/autenticacao.py listar
    python src/operador/autenticacao.py desativar <usuario>
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from perfis import PERFIS

MAX_TENTATIVAS = 5
BLOQUEIO_MIN = 5
SESSAO_MIN = 30
SENHA_MIN = 8
MSG_INCORRETO = "Usuário ou senha incorretos."
MSG_BLOQUEADO = f"Muitas tentativas erradas. Acesso bloqueado por {BLOQUEIO_MIN} minutos."
_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)
_SAL_FALSO = bytes(16)      # usuário inexistente: calcula o hash do mesmo jeito (tempo parecido)

BANCO = Path(__file__).resolve().parents[2] / "data" / "processed" / "seguranca_viaria.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    usuario       TEXT PRIMARY KEY,
    nome          TEXT NOT NULL,
    perfil        TEXT NOT NULL CHECK (perfil IN ('transito', 'saude', 'gestao')),
    hash          TEXT NOT NULL,
    sal           TEXT NOT NULL,
    tentativas    INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate TEXT,
    ativo         INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acessos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    usuario   TEXT NOT NULL,
    evento    TEXT NOT NULL CHECK (evento IN ('entrada', 'falha', 'bloqueio', 'saida', 'expirou'))
);
"""


@dataclass(frozen=True)
class Usuario:
    usuario: str
    nome: str
    perfil: str


@dataclass(frozen=True)
class Resultado:
    ok: bool
    usuario: Usuario | None = None
    mensagem: str = ""


def migrar(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)


def _hash(senha: str, sal: bytes) -> bytes:
    return hashlib.scrypt(senha.encode("utf-8"), salt=sal, **_SCRYPT)


def _agora(agora):
    return (agora or datetime.now()).replace(microsecond=0)


def criar_usuario(con, usuario: str, perfil: str, nome: str, senha: str) -> None:
    usuario = usuario.strip().lower()
    if not usuario or not nome.strip():
        raise ValueError("usuário e nome são obrigatórios")
    if perfil not in PERFIS:
        raise ValueError(f"perfil deve ser um de {sorted(PERFIS)}")
    if len(senha) < SENHA_MIN:
        raise ValueError(f"a senha precisa de pelo menos {SENHA_MIN} caracteres")
    sal = os.urandom(16)
    try:
        with con:
            con.execute("INSERT INTO usuarios (usuario, nome, perfil, hash, sal, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
                        (usuario, nome.strip(), perfil, _hash(senha, sal).hex(), sal.hex(),
                         _agora(None).isoformat()))
    except sqlite3.IntegrityError:
        raise ValueError(f"o usuário {usuario!r} já existe") from None


def registrar_acesso(con, usuario: str, evento: str, agora: datetime | None = None) -> None:
    with con:
        con.execute("INSERT INTO acessos (timestamp, usuario, evento) VALUES (?, ?, ?)",
                    (_agora(agora).isoformat(), usuario, evento))


def autenticar(con, usuario: str, senha: str, agora: datetime | None = None) -> Resultado:
    agora = _agora(agora)
    usuario = (usuario or "").strip().lower()
    linha = con.execute("SELECT nome, perfil, hash, sal, tentativas, bloqueado_ate FROM usuarios "
                        "WHERE usuario = ? AND ativo = 1", (usuario,)).fetchone()
    if linha is None:
        _hash(senha or "", _SAL_FALSO)
        return Resultado(False, mensagem=MSG_INCORRETO)
    nome, perfil, h, sal, tentativas, bloqueado_ate = linha
    if bloqueado_ate and agora < datetime.fromisoformat(bloqueado_ate):
        return Resultado(False, mensagem=MSG_BLOQUEADO)
    if bloqueado_ate:            # o bloqueio expirou: recomeça a contagem
        tentativas = 0
    if hmac.compare_digest(_hash(senha or "", bytes.fromhex(sal)), bytes.fromhex(h)):
        with con:
            con.execute("UPDATE usuarios SET tentativas = 0, bloqueado_ate = NULL WHERE usuario = ?", (usuario,))
        registrar_acesso(con, usuario, "entrada", agora)
        return Resultado(True, Usuario(usuario, nome, perfil))
    tentativas += 1
    bloqueio = (agora + timedelta(minutes=BLOQUEIO_MIN)).isoformat() if tentativas >= MAX_TENTATIVAS else None
    with con:
        con.execute("UPDATE usuarios SET tentativas = ?, bloqueado_ate = ? WHERE usuario = ?",
                    (0 if bloqueio else tentativas, bloqueio, usuario))
    registrar_acesso(con, usuario, "bloqueio" if bloqueio else "falha", agora)
    return Resultado(False, mensagem=MSG_BLOQUEADO if bloqueio else MSG_INCORRETO)


def sessao_valida(ultimo_uso: datetime | None, agora: datetime | None = None) -> bool:
    return ultimo_uso is not None and _agora(agora) - ultimo_uso <= timedelta(minutes=SESSAO_MIN)


def main(argv=None):
    import argparse
    import getpass
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Usuários da interface do operador BetterWay")
    p.add_argument("--db", default=str(BANCO))
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("criar")
    c.add_argument("usuario")
    c.add_argument("perfil", choices=sorted(PERFIS))
    c.add_argument("nome")
    sub.add_parser("listar")
    dsat = sub.add_parser("desativar")
    dsat.add_argument("usuario")
    a = p.parse_args(argv)
    con = sqlite3.connect(a.db)
    migrar(con)
    if a.cmd == "criar":
        senha = getpass.getpass("senha: ")
        if senha != getpass.getpass("repita a senha: "):
            sys.exit("as senhas não conferem")
        try:
            criar_usuario(con, a.usuario, a.perfil, a.nome, senha)
        except ValueError as erro:
            sys.exit(str(erro))
        print(f"usuário {a.usuario} criado ({PERFIS[a.perfil]})")
    elif a.cmd == "listar":
        for u, n, pf, at in con.execute("SELECT usuario, nome, perfil, ativo FROM usuarios ORDER BY perfil, usuario"):
            print(f"{u:<14} {PERFIS[pf]:<9} {'ativo' if at else 'inativo':<8} {n}")
    else:
        with con:
            n = con.execute("UPDATE usuarios SET ativo = 0 WHERE usuario = ?", (a.usuario.lower(),)).rowcount
        print("desativado" if n else "usuário não encontrado")


if __name__ == "__main__":
    main()
