"""Convite pela Gestão e segundo fator (TOTP, RFC 6238) — src/operador/totp.py e autenticacao.py."""
import sqlite3
from datetime import datetime, timedelta

import pytest

import autenticacao as au
import totp

T0 = datetime(2026, 11, 18, 14, 0)


def test_codigo_bate_com_o_vetor_da_rfc_6238():
    # RFC 6238, apêndice B: segredo ASCII "12345678901234567890", T = 59 s → 94287082 (8 dígitos)
    segredo = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp.codigo(segredo, 59, digitos=8) == "94287082"
    assert totp.codigo(segredo, 1111111109, digitos=8) == "07081804"


def test_verificar_aceita_o_passo_vizinho_e_recusa_o_resto():
    s = totp.gerar_segredo()
    t = 1_800_000_000
    assert totp.verificar(s, totp.codigo(s, t), t)
    assert totp.verificar(s, totp.codigo(s, t - 30), t)          # relógio do celular um pouco atrasado
    assert not totp.verificar(s, totp.codigo(s, t - 120), t)
    assert not totp.verificar(s, "12345", t) and not totp.verificar(s, "abcdef", t)


def test_uri_para_o_aplicativo():
    u = totp.uri("ABCDEF234567", "saude1")
    assert u.startswith("otpauth://totp/BetterWay:saude1?") and "secret=ABCDEF234567" in u and "issuer=BetterWay" in u


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    au.migrar(c)
    return c


def _aceitar(con, token, agora=T0):
    segredo = totp.gerar_segredo()
    u = au.aceitar_convite(con, token, "senha-forte-1", totp.codigo(segredo, agora.timestamp()), segredo, agora=agora)
    return u, segredo


def test_convite_cria_a_conta_e_exige_o_codigo_para_entrar(con):
    token = au.convidar(con, "saude2", "saude", "Operador(a) Saúde 2", "saude2@exemplo.org", agora=T0)
    assert au.dados_convite(con, token, agora=T0).nome == "Operador(a) Saúde 2"
    u, segredo = _aceitar(con, token)
    assert u.perfil == "saude"
    r = au.autenticar(con, "saude2", "senha-forte-1", agora=T0)
    assert not r.ok and r.precisa_codigo
    errado = au.verificar_codigo(con, "saude2", "000000", agora=T0)
    assert not errado.ok
    certo = au.verificar_codigo(con, "saude2", totp.codigo(segredo, T0.timestamp()), agora=T0)
    assert certo.ok and certo.usuario.usuario == "saude2"


def test_convite_so_vale_uma_vez_e_expira(con):
    token = au.convidar(con, "transito2", "transito", "T2", "t2@exemplo.org", agora=T0)
    _aceitar(con, token)
    with pytest.raises(ValueError):
        _aceitar(con, token)
    velho = au.convidar(con, "transito3", "transito", "T3", "t3@exemplo.org", agora=T0)
    assert au.dados_convite(con, velho, agora=T0 + timedelta(hours=25)) is None


def test_token_do_convite_nao_fica_guardado_em_claro(con):
    token = au.convidar(con, "gestao2", "gestao", "G2", "g2@exemplo.org", agora=T0)
    assert token not in str(list(con.execute("SELECT * FROM usuarios")))


def test_aceitar_exige_o_codigo_certo_e_senha_forte(con):
    token = au.convidar(con, "saude3", "saude", "S3", "s3@exemplo.org", agora=T0)
    segredo = totp.gerar_segredo()
    with pytest.raises(ValueError):
        au.aceitar_convite(con, token, "senha-forte-1", "000000", segredo, agora=T0)
    with pytest.raises(ValueError):
        au.aceitar_convite(con, token, "curta", totp.codigo(segredo, T0.timestamp()), segredo, agora=T0)


def test_quem_ainda_nao_aceitou_o_convite_nao_entra(con):
    au.convidar(con, "saude4", "saude", "S4", "s4@exemplo.org", agora=T0)
    assert not au.autenticar(con, "saude4", "qualquer-senha", agora=T0).ok


def test_codigos_errados_tambem_bloqueiam(con):
    token = au.convidar(con, "saude5", "saude", "S5", "s5@exemplo.org", agora=T0)
    _, segredo = _aceitar(con, token)
    for _ in range(au.MAX_TENTATIVAS):
        au.verificar_codigo(con, "saude5", "000000", agora=T0)
    r = au.verificar_codigo(con, "saude5", totp.codigo(segredo, T0.timestamp()), agora=T0 + timedelta(minutes=1))
    assert not r.ok and r.mensagem == au.MSG_BLOQUEADO


def test_usuario_repetido_no_convite_e_recusado(con):
    au.convidar(con, "saude6", "saude", "S6", "s6@exemplo.org", agora=T0)
    with pytest.raises(ValueError):
        au.convidar(con, "saude6", "saude", "S6", "s6@exemplo.org", agora=T0)


def test_so_a_gestao_convida():
    import perfis
    assert perfis.pode("gestao", "convidar") and not perfis.pode("transito", "convidar")
