"""Perfil de cada pessoa (src/operador/autenticacao.py): login pelo e-mail, foto, cargo, área só pela Gestão."""
import io
import sqlite3
from datetime import datetime

import pytest
from PIL import Image

import autenticacao as au
import totp

T0 = datetime(2026, 11, 18, 15, 0)


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    au.migrar(c)
    return c


def _ativar(con, email, area="saude", nome="Ana Souza", cargo="Médica reguladora"):
    token = au.convidar_pessoa(con, email=email, area=area, nome=nome, cargo=cargo, orgao="Central de regulação",
                               matricula="12345", agora=T0)
    seg = totp.gerar_segredo()
    u = au.aceitar_convite(con, token, "senha-forte-1", totp.codigo(seg, T0.timestamp()), seg, agora=T0)
    return u, seg


def test_usuario_vem_do_email_e_o_login_aceita_o_email(con):
    u, _ = _ativar(con, "Ana.Souza@saude.exemplo.org")
    assert u.usuario == "ana.souza"
    r = au.autenticar(con, "ana.souza@saude.exemplo.org", "senha-forte-1", agora=T0)
    assert r.precisa_codigo and r.usuario.usuario == "ana.souza"


def test_dois_emails_com_o_mesmo_comeco_ganham_usuarios_diferentes(con):
    a, _ = _ativar(con, "ana.souza@saude.exemplo.org")
    b, _ = _ativar(con, "ana.souza@transito.exemplo.org", area="transito")
    assert a.usuario != b.usuario


def test_perfil_traz_os_campos_e_o_nome_de_tratamento(con):
    u, _ = _ativar(con, "ana.souza@saude.exemplo.org", nome="Ana Paula Souza")
    p = au.perfil(con, u.usuario)
    assert p.nome == "Ana Paula Souza" and p.cargo == "Médica reguladora" and p.area == "saude"
    assert p.primeiro_nome == "Ana" and p.matricula == "12345" and p.foto is None


def test_a_pessoa_edita_o_proprio_perfil_mas_nao_a_area(con):
    u, _ = _ativar(con, "ana.souza@saude.exemplo.org")
    au.atualizar_perfil(con, u.usuario, por=u.usuario, nome_tratamento="Aninha", telefone="11 99999-0000",
                        turno="Manhã")
    p = au.perfil(con, u.usuario)
    assert p.primeiro_nome == "Aninha" and p.telefone == "11 99999-0000" and p.turno == "Manhã"
    with pytest.raises(PermissionError):
        au.atualizar_perfil(con, u.usuario, por=u.usuario, area="gestao")


def test_so_a_gestao_muda_area_cargo_e_desativa(con):
    g, _ = _ativar(con, "chefe@prefeitura.exemplo.org", area="gestao", nome="Carla Lima", cargo="Coordenadora")
    u, _ = _ativar(con, "ana.souza@saude.exemplo.org")
    au.atualizar_perfil(con, u.usuario, por=g.usuario, area="transito", cargo="Operadora de tráfego")
    assert au.perfil(con, u.usuario).area == "transito"
    with pytest.raises(PermissionError):
        au.atualizar_perfil(con, g.usuario, por=u.usuario, cargo="Hacker")
    au.desativar(con, u.usuario, por=g.usuario)
    assert not au.autenticar(con, "ana.souza", "senha-forte-1", agora=T0).precisa_codigo


def test_foto_e_reduzida_e_quadrada(con):
    u, _ = _ativar(con, "ana.souza@saude.exemplo.org")
    buf = io.BytesIO()
    Image.new("RGB", (1200, 800), (0, 194, 122)).save(buf, "JPEG")
    au.salvar_foto(con, u.usuario, buf.getvalue(), por=u.usuario)
    foto = Image.open(io.BytesIO(au.perfil(con, u.usuario).foto))
    assert foto.size == (256, 256)
    with pytest.raises(ValueError):
        au.salvar_foto(con, u.usuario, b"nao e imagem", por=u.usuario)


def test_trocar_senha_exige_a_atual(con):
    u, _ = _ativar(con, "ana.souza@saude.exemplo.org")
    with pytest.raises(ValueError):
        au.trocar_senha(con, u.usuario, "errada-errada", "nova-senha-123")
    au.trocar_senha(con, u.usuario, "senha-forte-1", "nova-senha-123")
    assert au.autenticar(con, "ana.souza", "nova-senha-123", agora=T0).precisa_codigo


def test_meus_acessos(con):
    u, seg = _ativar(con, "ana.souza@saude.exemplo.org")
    au.verificar_codigo(con, u.usuario, totp.codigo(seg, T0.timestamp()), agora=T0)
    assert [a["evento"] for a in au.meus_acessos(con, u.usuario)][:1] == ["entrada"]
