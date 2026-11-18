"""Autenticação da plataforma BetterWay.

Contas criadas pela Gestão por convite (link de uso único, 24 h, guardado só como hash); a própria pessoa define a
senha e liga o segundo fator (código de 6 dígitos de um aplicativo autenticador, TOTP). Senha com scrypt e sal por
usuário, comparação em tempo constante, bloqueio após 5 erros (de senha ou de código), sessão de 30 min.

    python src/operador/autenticacao.py convidar <email> <area> "<nome completo>" --cargo "..."   # imprime o link
    python src/operador/autenticacao.py criar <usuario> <perfil> "<nome exibido>"     # conta sem convite (testes)
    python src/operador/autenticacao.py listar
    python src/operador/autenticacao.py desativar <usuario>
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import totp
from perfis import PERFIS

MAX_TENTATIVAS = 5
BLOQUEIO_MIN = 5
SESSAO_MIN = 30
CONVITE_H = 24
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
    evento    TEXT NOT NULL CHECK (evento IN ('entrada', 'falha', 'bloqueio', 'saida', 'expirou', 'convite',
                                            'convite_aceito', 'codigo_errado'))
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
    precisa_codigo: bool = False      # senha certa; falta o código do aplicativo


_COLUNAS_NOVAS = {"email": "TEXT", "totp": "TEXT", "convite_hash": "TEXT", "convite_expira": "TEXT",
                  "nome_tratamento": "TEXT", "cargo": "TEXT", "orgao": "TEXT", "matricula": "TEXT",
                  "telefone": "TEXT", "turno": "TEXT", "foto": "BLOB", "atualizado_em": "TEXT"}


def migrar(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    tem = {r[1] for r in con.execute("PRAGMA table_info(usuarios)")}
    with con:
        for col, tipo in _COLUNAS_NOVAS.items():
            if col not in tem:
                con.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {tipo}")
    # bancos antigos: a tabela acessos foi criada com menos tipos de evento; recria mantendo as linhas
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name = 'acessos'").fetchone()[0]
    if "codigo_errado" not in sql:
        with con:
            con.execute("ALTER TABLE acessos RENAME TO acessos_antigo")
            con.executescript(SCHEMA)
            con.execute("INSERT INTO acessos (id, timestamp, usuario, evento) "
                        "SELECT id, timestamp, usuario, evento FROM acessos_antigo")
            con.execute("DROP TABLE acessos_antigo")


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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


def convidar(con, usuario: str, perfil: str, nome: str, email: str, agora: datetime | None = None) -> str:
    """Cria a conta sem senha e devolve o token do convite (vale uma vez, por CONVITE_H horas). Só o hash é guardado."""
    usuario = usuario.strip().lower()
    if not usuario or not nome.strip() or "@" not in (email or ""):
        raise ValueError("usuário, nome e e-mail são obrigatórios")
    if perfil not in PERFIS:
        raise ValueError(f"perfil deve ser um de {sorted(PERFIS)}")
    agora = _agora(agora)
    token = secrets.token_urlsafe(24)
    try:
        with con:
            con.execute("INSERT INTO usuarios (usuario, nome, perfil, hash, sal, criado_em, email, convite_hash, "
                        "convite_expira) VALUES (?, ?, ?, '', '', ?, ?, ?, ?)",
                        (usuario, nome.strip(), perfil, agora.isoformat(), email.strip(), _sha(token),
                         (agora + timedelta(hours=CONVITE_H)).isoformat()))
    except sqlite3.IntegrityError:
        raise ValueError(f"o usuário {usuario!r} já existe") from None
    registrar_acesso(con, usuario, "convite", agora)
    return token


def dados_convite(con, token: str, agora: datetime | None = None) -> Usuario | None:
    linha = con.execute("SELECT usuario, nome, perfil, convite_expira FROM usuarios WHERE convite_hash = ? AND ativo = 1",
                        (_sha(token or ""),)).fetchone()
    if linha is None or _agora(agora) > datetime.fromisoformat(linha[3]):
        return None
    return Usuario(linha[0], linha[1], linha[2])


def aceitar_convite(con, token: str, senha: str, codigo_app: str, segredo: str,
                    agora: datetime | None = None) -> Usuario:
    """A pessoa define a senha e prova que o aplicativo autenticador está configurado (o 1º código)."""
    agora = _agora(agora)
    u = dados_convite(con, token, agora)
    if u is None:
        raise ValueError("convite inválido ou vencido")
    if len(senha or "") < SENHA_MIN:
        raise ValueError(f"a senha precisa de pelo menos {SENHA_MIN} caracteres")
    if not totp.verificar(segredo, codigo_app, agora.timestamp()):
        raise ValueError("o código do aplicativo não confere")
    sal = os.urandom(16)
    with con:
        con.execute("UPDATE usuarios SET hash = ?, sal = ?, totp = ?, convite_hash = NULL, convite_expira = NULL, "
                    "tentativas = 0, bloqueado_ate = NULL WHERE usuario = ?",
                    (_hash(senha, sal).hex(), sal.hex(), segredo, u.usuario))
    registrar_acesso(con, u.usuario, "convite_aceito", agora)
    return u


def _falha(con, usuario: str, tentativas: int, agora: datetime, evento: str) -> Resultado:
    tentativas += 1
    bloqueio = (agora + timedelta(minutes=BLOQUEIO_MIN)).isoformat() if tentativas >= MAX_TENTATIVAS else None
    with con:
        con.execute("UPDATE usuarios SET tentativas = ?, bloqueado_ate = ? WHERE usuario = ?",
                    (0 if bloqueio else tentativas, bloqueio, usuario))
    registrar_acesso(con, usuario, "bloqueio" if bloqueio else evento, agora)
    return Resultado(False, mensagem=MSG_BLOQUEADO if bloqueio else
                     ("Código do aplicativo incorreto." if evento == "codigo_errado" else MSG_INCORRETO))


def verificar_codigo(con, usuario: str, codigo_app: str, agora: datetime | None = None) -> Resultado:
    """2ª etapa do login: o código de 6 dígitos do aplicativo."""
    agora = _agora(agora)
    usuario = (usuario or "").strip().lower()
    linha = con.execute("SELECT nome, perfil, totp, tentativas, bloqueado_ate FROM usuarios WHERE usuario = ? AND "
                        "ativo = 1", (usuario,)).fetchone()
    if linha is None or not linha[2]:
        return Resultado(False, mensagem=MSG_INCORRETO)
    nome, perfil, segredo, tentativas, bloqueado_ate = linha
    if bloqueado_ate and agora < datetime.fromisoformat(bloqueado_ate):
        return Resultado(False, mensagem=MSG_BLOQUEADO)
    if bloqueado_ate:
        tentativas = 0
    if totp.verificar(segredo, codigo_app, agora.timestamp()):
        with con:
            con.execute("UPDATE usuarios SET tentativas = 0, bloqueado_ate = NULL WHERE usuario = ?", (usuario,))
        registrar_acesso(con, usuario, "entrada", agora)
        return Resultado(True, Usuario(usuario, nome, perfil))
    return _falha(con, usuario, tentativas, agora, "codigo_errado")


def registrar_acesso(con, usuario: str, evento: str, agora: datetime | None = None) -> None:
    with con:
        con.execute("INSERT INTO acessos (timestamp, usuario, evento) VALUES (?, ?, ?)",
                    (_agora(agora).isoformat(), usuario, evento))


def autenticar(con, usuario: str, senha: str, agora: datetime | None = None) -> Resultado:
    agora = _agora(agora)
    usuario = _resolver(con, usuario)
    linha = con.execute("SELECT nome, perfil, hash, sal, tentativas, bloqueado_ate, totp FROM usuarios "
                        "WHERE usuario = ? AND ativo = 1", (usuario,)).fetchone()
    if linha is None or not linha[2]:            # inexistente ou convite ainda não aceito
        _hash(senha or "", _SAL_FALSO)
        return Resultado(False, mensagem=MSG_INCORRETO)
    nome, perfil, h, sal, tentativas, bloqueado_ate, segredo = linha
    if bloqueado_ate and agora < datetime.fromisoformat(bloqueado_ate):
        return Resultado(False, mensagem=MSG_BLOQUEADO)
    if bloqueado_ate:            # o bloqueio expirou: recomeça a contagem
        tentativas = 0
    if hmac.compare_digest(_hash(senha or "", bytes.fromhex(sal)), bytes.fromhex(h)):
        if segredo:                              # falta o código do aplicativo (as tentativas continuam contando)
            return Resultado(False, Usuario(usuario, nome, perfil), precisa_codigo=True)
        with con:
            con.execute("UPDATE usuarios SET tentativas = 0, bloqueado_ate = NULL WHERE usuario = ?", (usuario,))
        registrar_acesso(con, usuario, "entrada", agora)
        return Resultado(True, Usuario(usuario, nome, perfil))
    return _falha(con, usuario, tentativas, agora, "falha")


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
    cv = sub.add_parser("convidar")
    cv.add_argument("email")
    cv.add_argument("area", choices=sorted(PERFIS))
    cv.add_argument("nome")
    cv.add_argument("--cargo", default="")
    cv.add_argument("--orgao", default="")
    cv.add_argument("--base", default="http://localhost:8611")
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
    elif a.cmd == "convidar":
        try:
            token = convidar_pessoa(con, email=a.email, area=a.area, nome=a.nome, cargo=a.cargo, orgao=a.orgao)
        except ValueError as erro:
            sys.exit(str(erro))
        print(f"convite para {a.email} (vale {CONVITE_H} h, uma vez): {a.base}/?convite={token}")
    elif a.cmd == "listar":
        for u, n, pf, at in con.execute("SELECT usuario, nome, perfil, ativo FROM usuarios ORDER BY perfil, usuario"):
            print(f"{u:<14} {PERFIS[pf]:<9} {'ativo' if at else 'inativo':<8} {n}")
    else:
        with con:
            n = con.execute("UPDATE usuarios SET ativo = 0 WHERE usuario = ?", (a.usuario.lower(),)).rowcount
        print("desativado" if n else "usuário não encontrado")




# ---------------------------------------------------------------- perfil de cada pessoa
_PESSOAIS = {"nome", "nome_tratamento", "telefone", "turno"}            # a própria pessoa edita
_DA_GESTAO = {"nome", "area", "cargo", "orgao", "matricula"}             # só a Gestão edita
FOTO_PX, FOTO_MAX_BYTES = 256, 5 * 1024 * 1024


@dataclass(frozen=True)
class Perfil:
    usuario: str
    nome: str
    nome_tratamento: str | None
    email: str | None
    area: str
    cargo: str | None
    orgao: str | None
    matricula: str | None
    telefone: str | None
    turno: str | None
    foto: bytes | None
    tem_codigo: bool
    ativo: bool
    convite_pendente: bool

    @property
    def primeiro_nome(self) -> str:
        return (self.nome_tratamento or self.nome or self.usuario).split()[0]


def _resolver(con, identificacao: str | None) -> str:
    """Aceita o usuário ou o e-mail."""
    ident = (identificacao or "").strip().lower()
    if "@" in ident:
        linha = con.execute("SELECT usuario FROM usuarios WHERE lower(email) = ?", (ident,)).fetchone()
        return linha[0] if linha else ident
    return ident


def usuario_de_email(con, email: str) -> str:
    import re
    base = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0].lower()) or "pessoa"
    candidato, n = base, 2
    while con.execute("SELECT 1 FROM usuarios WHERE usuario = ?", (candidato,)).fetchone():
        candidato, n = f"{base}.{n}", n + 1
    return candidato


def convidar_pessoa(con, *, email: str, area: str, nome: str, cargo: str = "", orgao: str = "", matricula: str = "",
                    agora: datetime | None = None) -> str:
    """Convite com os dados do perfil; o usuário de login sai do e-mail (e a pessoa também entra pelo e-mail)."""
    if con.execute("SELECT 1 FROM usuarios WHERE lower(email) = ?", ((email or "").strip().lower(),)).fetchone():
        raise ValueError("já existe uma conta com este e-mail")
    usuario = usuario_de_email(con, email or "")
    token = convidar(con, usuario, area, nome, email, agora=agora)
    with con:
        con.execute("UPDATE usuarios SET cargo = ?, orgao = ?, matricula = ? WHERE usuario = ?",
                    (cargo.strip() or None, orgao.strip() or None, matricula.strip() or None, usuario))
    return token


def perfil(con, usuario: str) -> Perfil | None:
    linha = con.execute("SELECT usuario, nome, nome_tratamento, email, perfil, cargo, orgao, matricula, telefone, "
                        "turno, foto, totp, ativo, convite_hash FROM usuarios WHERE usuario = ?",
                        (_resolver(con, usuario),)).fetchone()
    if linha is None:
        return None
    u, nome, trat, email, area, cargo, orgao, mat, tel, turno, foto, segredo, ativo, conv = linha
    return Perfil(u, nome, trat, email, area, cargo, orgao, mat, tel, turno, foto, bool(segredo), bool(ativo),
                  bool(conv))


def equipe(con) -> list[Perfil]:
    return [perfil(con, r[0]) for r in con.execute("SELECT usuario FROM usuarios ORDER BY perfil, nome")]


def _area_de(con, usuario: str) -> str | None:
    linha = con.execute("SELECT perfil FROM usuarios WHERE usuario = ? AND ativo = 1", (usuario,)).fetchone()
    return linha[0] if linha else None


def atualizar_perfil(con, usuario: str, *, por: str, **campos) -> None:
    """A pessoa edita os próprios dados pessoais; área, cargo, órgão e matrícula só a Gestão muda."""
    gestao = _area_de(con, por) == "gestao"
    permitidos = (_PESSOAIS | _DA_GESTAO) if gestao else (_PESSOAIS if por == usuario else set())
    proibidos = set(campos) - permitidos
    if proibidos:
        raise PermissionError(f"sem permissão para mudar: {', '.join(sorted(proibidos))}")
    if "area" in campos and campos["area"] not in PERFIS:
        raise ValueError("área inválida")
    colunas = {("perfil" if k == "area" else k): ((v or "").strip() or None) if k != "area" else v
               for k, v in campos.items()}
    if not colunas:
        return
    if "nome" in colunas and not colunas["nome"]:
        raise ValueError("o nome não pode ficar vazio")
    sets = ", ".join(f"{k} = ?" for k in colunas)
    with con:
        con.execute(f"UPDATE usuarios SET {sets}, atualizado_em = ? WHERE usuario = ?",
                    (*colunas.values(), _agora(None).isoformat(), usuario))


def desativar(con, usuario: str, *, por: str) -> None:
    if _area_de(con, por) != "gestao" or por == usuario:
        raise PermissionError("só a Gestão desativa contas, e não a própria")
    with con:
        con.execute("UPDATE usuarios SET ativo = 0, atualizado_em = ? WHERE usuario = ?",
                    (_agora(None).isoformat(), usuario))


def salvar_foto(con, usuario: str, dados: bytes, *, por: str) -> None:
    """Corta no centro, reduz para 256 × 256 e guarda como JPEG (a foto original não é guardada)."""
    import io
    from PIL import Image, UnidentifiedImageError
    if por != usuario and _area_de(con, por) != "gestao":
        raise PermissionError("só a própria pessoa (ou a Gestão) muda a foto")
    if len(dados) > FOTO_MAX_BYTES:
        raise ValueError("a foto precisa ter até 5 MB")
    try:
        im = Image.open(io.BytesIO(dados)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise ValueError("arquivo não é uma imagem") from None
    lado = min(im.size)
    x, y = (im.width - lado) // 2, (im.height - lado) // 2
    im = im.crop((x, y, x + lado, y + lado)).resize((FOTO_PX, FOTO_PX), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    with con:
        con.execute("UPDATE usuarios SET foto = ?, atualizado_em = ? WHERE usuario = ?",
                    (buf.getvalue(), _agora(None).isoformat(), usuario))


def trocar_senha(con, usuario: str, atual: str, nova: str) -> None:
    linha = con.execute("SELECT hash, sal FROM usuarios WHERE usuario = ? AND ativo = 1", (usuario,)).fetchone()
    if linha is None or not linha[0] or not hmac.compare_digest(_hash(atual or "", bytes.fromhex(linha[1])),
                                                                 bytes.fromhex(linha[0])):
        raise ValueError("a senha atual não confere")
    if len(nova or "") < SENHA_MIN:
        raise ValueError(f"a senha nova precisa de pelo menos {SENHA_MIN} caracteres")
    sal = os.urandom(16)
    with con:
        con.execute("UPDATE usuarios SET hash = ?, sal = ?, atualizado_em = ? WHERE usuario = ?",
                    (_hash(nova, sal).hex(), sal.hex(), _agora(None).isoformat(), usuario))


def meus_acessos(con, usuario: str, n: int = 10) -> list[dict]:
    return [{"timestamp": t, "evento": e} for t, e in con.execute(
        "SELECT timestamp, evento FROM acessos WHERE usuario = ? ORDER BY id DESC LIMIT ?", (usuario, n))]


if __name__ == "__main__":
    main()
