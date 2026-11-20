"""Plataforma BetterWay: visão geral, painel de risco, ocorrências, sala de controle e estudos, por perfil.

    streamlit run src/operador/app.py          (de 1TIAO/GLOBAL-SOLUTION-2)

Antes, crie os usuários (senhas fora do Git):
    python src/operador/autenticacao.py criar gestao1 gestao "Gestão 1"

Specs: docs/specs/2026-11-17-interface-operador-design.md. Marca: kit BetterWay v2 (tema escuro, Montserrat).
O banco pode ser trocado por VIA_SEGURA_DB; BETTERWAY_SEM_MQTT=1 roda sem broker e BETTERWAY_SEM_CLIPES=1 sem
vídeos (testes).
"""
from __future__ import annotations

import json
from contextlib import contextmanager
import os
import sqlite3
import time as time_mod
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
for p in (AQUI, RAIZ / "src" / "central", RAIZ / "src" / "estudo_b_risco_vida"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import autenticacao as au  # noqa: E402
import componentes as cp  # noqa: E402
import camera as cam  # noqa: E402
import estilo as es  # noqa: E402
import leitura as lt  # noqa: E402
import mensagens as m  # noqa: E402
import ocorrencias as oc  # noqa: E402
import padrao as pdr  # noqa: E402
import registros as rg  # noqa: E402
import sinais as sn  # noqa: E402
import cartoes as ct  # noqa: E402
import leitor  # noqa: E402
import visao_geral as vg  # noqa: E402
from no_ao_vivo import CENARIOS, NoAoVivo, comando_cenario  # noqa: E402
from perfis import PERFIS, SemPermissao, exigir, pode  # noqa: E402

DB = Path(os.environ.get("VIA_SEGURA_DB", RAIZ / "data" / "processed" / "seguranca_viaria.db"))
EVID = RAIZ / "docs" / "evidencias"
MARCA = RAIZ / "assets" / "marca"
PILOTO, LAT, LON = 139, -23.54183, -46.61613          # Largo da Concórdia (Brás)
VIDEO_DEMO = "cdmx_pexels_25775484"
# lema da BetterWay (login e Visão geral); a segunda metade sai em verde
LEMA = "To live, to move, <span>to drive, to be free.</span>"
CLIPE_PILOTO = "cadeirante_03"          # CAM 01 (Largo da Concórdia): cadeira de rodas na faixa
# vídeos da rede de câmeras (os de 19/11, com a faixa de cada um); a ambulância entra quando o vídeo dela estiver pronto
CLIPES_REDE = ("cadeirante_03", "andador_01", "ambulancia_01", "infracao_01", "normal_02")
ROTULOS_CENARIO = {"normal": "Normal", "pedestre": "Pedestre", "camera_tempo": "Câmera pede mais tempo",
                   "escola": "Escola", "chuva": "Chuva", "alagamento": "Alagamento", "ambulancia": "Ambulância"}
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


# ---------------------------------------------------------------- dados
def conexao() -> sqlite3.Connection:
    con = sqlite3.connect(DB, check_same_thread=False, timeout=10)
    au.migrar(con)
    oc.migrar(con)
    lt.migrar(con)
    return con


def consultar(sql: str, params=()) -> pd.DataFrame:
    try:
        return pd.read_sql_query(sql, conexao(), params=params)
    except (sqlite3.Error, pd.errors.DatabaseError):
        return pd.DataFrame()


@st.cache_resource
def no_ao_vivo() -> NoAoVivo:
    if os.environ.get("BETTERWAY_SEM_MQTT"):
        return NoAoVivo()
    return NoAoVivo.conectar(banco=str(DB))


@st.cache_data(ttl=600, show_spinner=False)
def risco_em(quando_iso: str, chuva: float) -> dict | None:
    try:
        from risco import risco
        return risco(LAT, LON, datetime.fromisoformat(quando_iso), chuva)
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def risco_medio_do_ponto(util: bool) -> float | None:
    """Média do risco relativo do piloto ao longo de um dia (útil ou fim de semana), sem chuva."""
    dia = datetime(2026, 11, 17) if util else datetime(2026, 11, 22)
    vals = [r["risco_relativo"] for h in range(24) if (r := risco_em(dia.replace(hour=h, minute=30).isoformat(), 0.0))]
    return sum(vals) / len(vals) if vals else None


@st.cache_data(ttl=600, show_spinner=False)
def chuva_agora() -> float | None:
    try:
        import fontes
        return fontes.chuva_prevista_mm_h(LAT, LON, datetime.now(m.FUSO))
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def clipes() -> list[cam.Clipe]:
    if os.environ.get("BETTERWAY_SEM_CLIPES"):
        return []
    return cam.clipes_disponiveis()


def camera_agora(agora: datetime) -> lt.Camera | None:
    """Últimos 10 min da visão; sem nada ao vivo, o vídeo de referência (demonstração)."""
    desde = (agora - timedelta(minutes=10)).isoformat(timespec="seconds")
    ev = consultar("SELECT tipo, payload_json FROM eventos WHERE origem = 'yolo' AND timestamp >= ?", (desde,))
    fonte = "ao vivo"
    if ev.empty:
        ev = consultar("SELECT tipo, payload_json FROM eventos WHERE origem = 'yolo' AND payload_json LIKE ?",
                       (f'%{VIDEO_DEMO}%',))
        fonte = "demo"
    if ev.empty:
        return None
    contar = lambda t: int((ev["tipo"] == t).sum())  # noqa: E731
    return lt.Camera(contar("pedestre_na_faixa"), contar("conflito_veiculo_pedestre"), contar("pcd_na_faixa"), fonte)


# ---------------------------------------------------------------- sessão
def usuario() -> au.Usuario | None:
    u, ultimo = st.session_state.get("usuario"), st.session_state.get("ultimo_uso")
    if u is None:
        return None
    if not au.sessao_valida(ultimo):
        au.registrar_acesso(conexao(), u.usuario, "expirou")
        st.session_state.clear()
        st.session_state["aviso_login"] = "Sua sessão expirou depois de 30 minutos sem uso. Entre de novo."
        return None
    st.session_state["ultimo_uso"] = datetime.now().replace(microsecond=0)
    return u


def _estatico(origem: Path) -> str:
    """Copia um arquivo da marca para a pasta servida pelo Streamlit (fora do Git) e devolve a URL relativa."""
    destino = AQUI / "static" / origem.name
    if origem.exists() and (not destino.exists() or destino.stat().st_size != origem.stat().st_size):
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(origem.read_bytes())
    return f"app/static/{origem.name}"


CSS_LOGIN = """
<style>
[data-testid="stHeader"] {{ display: none; }}
[data-testid="stAppViewContainer"] {{ background: #0B0F12 url("{poster}") 40% center / cover no-repeat; }}
[data-testid="stMain"] {{ position: relative; z-index: 1; background: transparent; }}
.bw-login-video {{ position: fixed; inset: 0; width: 100vw; height: 100vh; object-fit: cover; object-position: 30% center;
  z-index: -2; pointer-events: none; }}
.bw-login-veu {{ position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background: radial-gradient(ellipse 36% 62% at 80% 46%, rgba(11,15,18,.74) 0%, rgba(11,15,18,.5) 50%,
              rgba(11,15,18,0) 100%); }}
[data-testid="stImage"] img {{ filter: drop-shadow(0 2px 10px rgba(0,0,0,.55)); }}
.bw-login-titulo, .bw-login-sub {{ text-shadow: 0 1px 12px rgba(0,0,0,.45); }}
[data-testid="stForm"] {{ background: rgba(20, 23, 27, .62) !important; backdrop-filter: blur(10px); }}
/* o login é sempre escuro (fica sobre o vídeo), qualquer que seja o tema escolhido */
.bw-login-titulo, .bw-login-sub, [data-testid="stForm"] label, [data-testid="stForm"] label p
  {{ color: #F4F4EF !important; }}
.bw-login-titulo span {{ color: #00C27A !important; }}
.bw-login-sub {{ color: #C9CBC6 !important; }}
[data-testid="stForm"] {{ border-color: #3A4047 !important; }}
[data-testid="stForm"] [data-baseweb="input"], [data-testid="stForm"] [data-baseweb="base-input"],
[data-testid="stForm"] input {{ background: #2A2E33 !important; color: #F4F4EF !important; border-color: #3A4047 !important; }}
[data-testid="stForm"] input::placeholder {{ color: #9AA1AA !important; }}
[data-testid="stForm"] [data-testid="stTextInputRootElement"] {{ background: #2A2E33 !important;
  border: 1px solid #3A4047 !important; }}
[data-testid="stForm"] [data-testid="stTextInputRootElement"]:focus-within {{ border-color: #00C27A !important; }}
[data-testid="stForm"] [data-baseweb="input"] div {{ background: #2A2E33 !important; }}
[data-testid="stForm"] [data-testid="stTextInputRootElement"] button {{ background: transparent !important;
  color: #C9CBC6 !important; }}
.block-container {{ padding-top: 0 !important; }}
.bw-login-espaco {{ height: 22vh; }}
.bw-login-titulo {{ font-size: clamp(26px, 2.6vw, 34px); font-weight: 700; line-height: 1.15; margin: 18px 0 8px; }}
.bw-login-titulo span {{ color: #00C27A; display: block; }}
.bw-login-sub {{ color: #C9CBC6; font-size: 15px; margin: 0 0 22px; }}
[data-testid="stForm"] {{ background: rgba(26, 29, 33, .78); backdrop-filter: blur(6px); }}
@media (max-width: 760px) {{
  .bw-login-video {{ height: 46vh; object-position: 42% center; }}
  .bw-login-veu {{ background: linear-gradient(to bottom, rgba(11,15,18,.05) 0, rgba(11,15,18,.35) 30vh, #0B0F12 46vh); }}
  [data-testid="stAppViewContainer"] {{ background: #0B0F12; }}
  .bw-login-espaco {{ height: 30vh; }}
}}
@media (prefers-reduced-motion: reduce) {{ .bw-login-video {{ display: none; }} }}
</style>
"""


def tela_login() -> None:
    poster = _estatico(MARCA / "login-video-poster.jpg")
    html(CSS_LOGIN.format(poster=poster))
    if (MARCA / "login-video-1080.mp4").exists():        # sem o vídeo, fica o primeiro quadro dele como imagem
        html(f'<video class="bw-login-video" src="{_estatico(MARCA / "login-video-1080.mp4")}" poster="{poster}" '
             f'autoplay muted loop playsinline aria-hidden="true"></video>')
    html('<div class="bw-login-veu"></div>')
    _, esquerda = st.columns([1.5, 0.85])                # formulário à direita: a cena do vídeo fica livre
    with esquerda:
        html('<div class="bw-login-espaco"></div>')
        logo = MARCA / "betterway-logo-horizontal-escuro.png"
        if logo.exists():
            st.image(str(logo), width=260)
        html(f'<div class="bw-login-titulo">{LEMA}</div>'
             '<p class="bw-login-sub">Entre com o usuário da sua equipe.</p>')
        if st.session_state.get("aviso_login"):
            st.info(st.session_state["aviso_login"])
        token = st.query_params.get("convite")
        if token:
            _aceitar_convite(token)
        elif st.session_state.get("login_pendente"):
            _segunda_etapa(st.session_state["login_pendente"])
        else:
            with st.form("login"):
                nome = st.text_input("E-mail ou usuário")
                senha = st.text_input("Senha", type="password")
                entrar = st.form_submit_button("Entrar", type="primary", width="stretch")
            if entrar:
                r = au.autenticar(conexao(), nome, senha)
                if r.ok:
                    _abrir_sessao(r.usuario)
                elif r.precisa_codigo:
                    st.session_state["login_pendente"] = r.usuario.usuario
                    st.rerun()
                else:
                    st.error(r.mensagem)


def _abrir_sessao(u: au.Usuario) -> None:
    st.session_state.clear()
    st.session_state["usuario"] = u
    st.session_state["ultimo_uso"] = datetime.now().replace(microsecond=0)
    # quem acabou de sair continua no endereço /sair: sem isto, a página de sair rodaria de novo logo após o login
    caminho = (st.context.url or "").split("?")[0].rstrip("/")
    if caminho.endswith("/sair"):
        st.session_state["ir_para"] = "visao"
    st.rerun()


def _segunda_etapa(usuario_: str) -> None:
    with st.form("codigo"):
        st.markdown("**Digite o código de 6 dígitos** que aparece no seu aplicativo autenticador.")
        codigo = st.text_input("Código do aplicativo", max_chars=6)
        ok = st.form_submit_button("Confirmar", type="primary", width="stretch")
    if ok:
        r = au.verificar_codigo(conexao(), usuario_, codigo)
        if r.ok:
            _abrir_sessao(r.usuario)
        else:
            st.error(r.mensagem)
    if st.button("Voltar", width="stretch"):
        st.session_state.pop("login_pendente", None)
        st.rerun()


def _aceitar_convite(token: str) -> None:
    import segno
    import totp
    con = conexao()
    u = au.dados_convite(con, token)
    if u is None:
        st.error("Este convite não vale mais. Peça um novo à equipe de Gestão.")
        return
    segredo = st.session_state.setdefault("segredo_convite", totp.gerar_segredo())
    st.markdown(f"**Olá, {es.esc(u.nome)}.** Crie sua senha e ligue o código do aplicativo para entrar na equipe de "
                f"{PERFIS[u.perfil]}.")
    html('<div style="background:#fff;border-radius:12px;padding:10px;display:inline-block">'
         + segno.make(totp.uri(segredo, u.usuario), error="m").svg_inline(scale=4) + "</div>")
    st.caption(f"Leia o QR Code com o Google Authenticator ou o Microsoft Authenticator. Sem câmera? Digite a chave: "
               f"{segredo}")
    with st.form("convite"):
        senha = st.text_input("Crie uma senha (mínimo de 8 caracteres)", type="password")
        senha2 = st.text_input("Repita a senha", type="password")
        codigo = st.text_input("Código que apareceu no aplicativo", max_chars=6)
        ok = st.form_submit_button("Ativar meu acesso", type="primary", width="stretch")
    if ok:
        if senha != senha2:
            st.error("As senhas não conferem.")
            return
        try:
            au.aceitar_convite(con, token, senha, codigo, segredo)
        except ValueError as erro:
            st.error(str(erro).capitalize() + ".")
            return
        st.session_state.pop("segredo_convite", None)
        st.query_params.clear()
        st.session_state["aviso_login"] = "Acesso ativado. Entre com seu usuário, sua senha e o código do aplicativo."
        st.rerun()


def sair() -> None:
    u = st.session_state.get("usuario")
    if u is not None:
        au.registrar_acesso(conexao(), u.usuario, "saida")
    st.session_state.clear()
    st.rerun()


def tema() -> str:
    """Tema da sessão: começa no do sistema e muda pelo botão de sol e lua."""
    if "tema" not in st.session_state:
        st.session_state["tema"] = "light" if st.context.theme.type == "light" else "dark"
    return st.session_state["tema"]


def _trocar_tema() -> None:
    st.session_state["tema"] = "dark" if tema() == "light" else "light"


@contextmanager
def cartao(chave: str, icone: str, titulo: str):
    """Bloco da página num cartão: ícone em círculo, título e o conteúdo (inclusive gráficos e botões) dentro."""
    with st.container(key=f"sup_{chave}"):
        html(f'<div class="bw-sup-topo"><span class="bw-chip">{es.icone(icone, es.DESTAQUE, 22)}</span>'
             f'<h3>{es.esc(titulo)}</h3></div>')
        yield


def html(conteudo: str) -> None:
    st.markdown(conteudo, unsafe_allow_html=True)


# ---------------------------------------------------------------- visão geral (demonstração)
def _calcular_leitura(quando: datetime, chuva: float | None, agora: datetime) -> lt.Leitura:
    hist = consultar("SELECT data_sinistro, hora, chuva_mm FROM sinistros WHERE cluster_id = ?", (PILOTO,))
    padrao = pdr.padrao_agora(hist, quando, chuva)
    rk = risco_em(quando.replace(second=0, microsecond=0).isoformat(), chuva or 0.0)
    media = risco_medio_do_ponto(quando.weekday() < 5)
    vezes_local = rk["risco_relativo"] / media if rk and media else None
    return lt.ler(padrao, camera_agora(agora), chuva, vezes_local, rk["risco_relativo"] if rk else None)


def _ir_cenario(i: int) -> None:
    st.session_state["vg_cenario"] = i


def _video_cenario(c: vg.Cenario) -> str:
    """O vídeo do cenário, já com o reconhecimento da visão (ou, sem ele, um espaço reservado)."""
    f = vg.video_do_cenario(c, vg.PASTA_VIDEOS, vg.PASTA_ANOTADOS)
    if f is None:
        return (f'<div class="bw-vg-video vazio"><div>{es.icone("camera", es.MUTED, 30)}'
                f'<b>Vídeo do cenário em breve</b><span>{es.esc(c.arquivo_video)}</span></div></div>')
    etiqueta = ('<span class="bw-vg-etiqueta">' + es.icone("camera", "#F5F5F2", 16) +
                ('Visão computacional · rostos e placas borrados' if f.name.endswith("_anotado.mp4")
                 else 'Vídeo de referência') + '</span>')
    return (f'<div class="bw-vg-video"><video src="{_estatico(f)}" autoplay muted loop playsinline '
            f'aria-label="{es.esc(c.titulo)}"></video>{etiqueta}</div>')


def _serie_risco(dia: datetime) -> list[float]:
    """Risco relativo à média da cidade, hora a hora, num dia como o de hoje (modelo do Estudo B)."""
    return [r["risco_relativo"] for h in range(24)
            if (r := risco_em(dia.replace(hour=h, minute=0, second=0, microsecond=0).isoformat(), 0.0))]


def _indicadores_vg() -> None:
    """Indicadores com números reais: o modelo de risco, o Estudo A (5 rodadas de 30 min no SUMO) e o nó da faixa."""
    agora = datetime.now(m.FUSO).replace(tzinfo=None)
    serie = _serie_risco(agora)
    rk = risco_em(agora.replace(second=0, microsecond=0).isoformat(), 0.0)
    cartoes = []
    if rk and serie:
        cartoes.append(es.indicador("grafico", f"{rk['risco_relativo']:.1f}×".replace(".", ","),
                                    "risco agora no Largo × média da cidade", "modelo de risco, hoje", serie))
    p = EVID / "estudo_a" / "estudo_a_resumo.csv"
    if p.exists():
        r = pd.read_csv(p, sep=";", encoding="utf-8-sig").set_index(["comparacao", "sistema"])
        sem, com = r.loc[("completo", "sem")], r.loc[("completo", "com")]
        faixa_s = sem.na_faixa_carros_verde_reduzida + sem.na_faixa_carros_verde_comum
        faixa_c = com.na_faixa_carros_verde_reduzida + com.na_faixa_carros_verde_comum
        cartoes.append(es.indicador("pedestre", f"{faixa_c:.0f}", "pessoas na faixa com carro em verde, por rodada",
                                    f"hoje são {faixa_s:.1f}".replace(".", ","), None, "−100%"))
        var = (com.tempo_ambulancia_s - sem.tempo_ambulancia_s) / sem.tempo_ambulancia_s * 100
        cartoes.append(es.indicador("ambulancia", f"{com.tempo_ambulancia_s:.1f} s".replace(".", ","),
                                    "para a ambulância passar o cruzamento",
                                    f"hoje leva {sem.tempo_ambulancia_s:.1f} s".replace(".", ","), None,
                                    f"{var:.0f}%".replace("-", "−")))
    no = no_ao_vivo()
    ok = no.conectado
    cartoes.append(es.status("ok" if ok else "alerta", "Central conectada ao nó da faixa" if ok else
                             "Central sem conexão com o nó", f"Modo do semáforo: "
                             f"{cam.NOMES_MODO.get((no.estado or {}).get('modo'), 'aguardando o nó')}"))
    html('<div class="bw-indicadores">' + "".join(cartoes) + "</div>")


def pagina_visao_geral() -> None:
    """Cinco cenários, um por vez. A câmera é a protagonista; a simulação mostra o que o semáforo faz; os
    indicadores dão os números reais; o texto só complementa."""
    i = st.session_state.get("vg_cenario", 0) % len(vg.CENARIOS)
    c = vg.CENARIOS[i]
    passos = [("camera", "Vê a faixa"), ("decide", "Entende o momento"), ("semaforo", "Ajusta o sinal na hora")]
    pilulas = "".join(f'<li class="{"ativo" if k == 0 else ""}"><span class="bw-chip">'
                      f'{es.icone(ic, "#1A1D21" if k == 0 else es.DESTAQUE, 20)}</span>{es.esc(t)}</li>'
                      for k, (ic, t) in enumerate(passos))
    html(f'<section class="bw-abertura"><div><div class="lema">{LEMA}</div><p>Os semáforos de hoje funcionam no '
         f'relógio: o tempo é o mesmo para todos, com ou sem gente na faixa. A BetterWay dá olhos ao semáforo.</p>'
         f'</div><ul>{pilulas}</ul></section>')
    col_cam, col_sim = st.columns([52, 48], gap="medium")
    with col_cam, st.container(key=f"vg_cena_{c.id}"):   # chave nova a cada cenário: a animação de entrada roda de novo
        topo, nav = st.columns([5, 2], vertical_alignment="center")
        with topo:
            html(f'<div class="bw-vg-topo"><span class="bw-chip">{es.icone("camera", es.DESTAQUE, 22)}</span><div>'
                 f'<div class="titulo">{es.esc(c.titulo)}<span class="bw-selo-ref">{es.esc(c.verbo)}</span></div>'
                 f'<p>{es.esc(c.texto)}</p></div></div>')
        with nav, st.container(horizontal=True, key="vg_setas", horizontal_alignment="right",
                               vertical_alignment="center", gap="small"):
            html(f'<span class="bw-nota bw-vg-conta">{i + 1} de {len(vg.CENARIOS)}</span>')
            st.button("Cenário anterior", key="vg_anterior", help="Cenário anterior",
                      on_click=_ir_cenario, args=(vg.anterior(i),))
            st.button("Próximo cenário", key="vg_proximo", help="Próximo cenário",
                      on_click=_ir_cenario, args=(vg.proximo(i),))
        html(_video_cenario(c))
    with col_sim, st.container(key="vg_sim"):
        html(f'<div class="bw-vg-topo"><span class="bw-chip">{es.icone("semaforo", es.DESTAQUE, 22)}</span><div>'
             f'<div class="titulo">O que o semáforo faz</div><p>Hoje × com a BetterWay, na simulação do Largo '
             f'(SUMO)</p></div></div>')
        _player(c.cena, compacto=True)
    _indicadores_vg()
    _pontos_cenario(i)


def _pontos_cenario(i: int) -> None:
    with st.container(horizontal=True, key="vg_pontos", vertical_alignment="center", gap="small"):
        for n, outro in enumerate(vg.CENARIOS):
            st.button(str(n + 1), key=f"vg_ponto_{n}", help=outro.titulo, disabled=n == i,
                      type="primary" if n == i else "secondary", on_click=_ir_cenario, args=(n,))
        st.page_link(PAGINAS["sobre"], label="Como funciona, de onde vêm os dados e a privacidade")


def _player(cena: str, compacto: bool = False) -> None:
    import cruzamento as cz
    try:
        dados, met = cz.carregar(cena)
    except FileNotFoundError:
        st.info("Cena ainda não exportada: rode `python src/simulacao/animacao_estudo_a.py --json`.")
        return
    components.html(cz.html_cruzamento(dados, met, compacto=compacto), height=510 if compacto else 800,
                    scrolling=False)


# ---------------------------------------------------------------- sobre
def pagina_sobre() -> None:
    cl = consultar("SELECT COUNT(*) AS n FROM clusters WHERE rank_urbano IS NOT NULL")
    n_grupos = int(cl.n.iloc[0]) if not cl.empty else None
    pil = consultar("SELECT COUNT(*) AS n, SUM(fatal) AS f FROM sinistros WHERE cluster_id = ?", (PILOTO,))
    n_pil, f_pil = (int(pil.n.iloc[0]), int(pil.f.iloc[0] or 0)) if not pil.empty else (None, None)
    st.title("Sobre a BetterWay")
    html(es.superficie("semaforo", "Um semáforo que enxerga a faixa",
                       "<p>Uma plataforma de segurança viária que junta dados reais de atropelamentos, uma câmera que "
                       "entende a faixa de pedestres e um semáforo conectado, para proteger quem atravessa e fazer o "
                       "trânsito andar. Sem identificar ninguém.</p>"))
    html('<div class="bw-secao">Como funciona, do começo ao fim</div>')
    passos = [("camera", "A câmera vê a faixa", "Conta quem atravessa, mede o tempo e percebe conflitos com veículos. "
               "Rostos e placas saem borrados."),
              ("decide", "A central decide", "Junta câmera, chuva, horário e o histórico do local, e escolhe o modo "
               "do semáforo."),
              ("semaforo", "O nó na faixa age", "O ESP32 estende o verde, avisa os motoristas no painel de LED ou dá "
               "prioridade à ambulância."),
              ("ok", "A equipe valida", "Trânsito confirma cada suspeita de acidente; Saúde recebe o alerta e "
               "despacha o atendimento.")]
    html('<div class="bw-passos2">' + "".join(
        es.superficie(ic, t, f"<p>{es.esc(d)}</p>").replace("</h3>", f'</h3><span class="n">{n} de 4</span>', 1)
        for n, (ic, t, d) in enumerate(passos, 1)) + "</div>")
    html('<div class="bw-secao">Onde a BetterWay funciona</div>')
    html('<p class="bw-nota" style="margin:-6px 0 14px;max-width:80ch">O piloto e as simulações são de um cruzamento, '
         'mas o que o sistema controla é a faixa e o semáforo. A mesma lógica serve em qualquer ponto com travessia '
         'ou sinal.</p>')
    lugares = [("pedestre", "Faixa no meio da quadra", "Sem cruzamento: o sinal da faixa espera quem ainda está "
                "atravessando e só libera os carros com a faixa vazia."),
               ("semaforo", "Cruzamento", "O verde vai para onde há carros e pessoas, e uma via vazia não segura o "
                "trânsito da outra."),
               ("escola", "Frente de escola", "Na entrada e na saída, toda travessia ganha mais tempo e o painel "
                "pede 30 km/h aos motoristas."),
               ("ambulancia", "Hospital e rota de emergência", "Os sinais no caminho abrem passagem para a "
                "ambulância e avisam quem está à frente."),
               ("rota", "Avenida e corredor de ônibus", "Vários nós na mesma avenida seguem o mesmo critério, "
                "faixa a faixa, sem depender de tempo fixo.")]
    html('<div class="bw-grade cinco">' + "".join(es.superficie(ic, ti, f"<p>{es.esc(tx)}</p>") for ic, ti, tx in lugares)
         + '</div>')
    with st.container(key="sup_barras"):
        _barras_sistema()
    piloto = (f"{n_pil} atropelamentos entre 2022 e 2025, {f_pil} com morte. " if n_pil else "") + \
        "Uma avenida de seis faixas com 16 metros de travessia: mais do que muita gente consegue atravessar no " \
        "tempo do verde." + (f" A plataforma ordena {n_grupos} pontos críticos urbanos da cidade." if n_grupos else "")
    dados = """<div class="bw-tempo">
          <div><span class="h">Acidentes</span><span>Infosiga-SP, atropelamentos de 2022 a 2025</span></div>
          <div><span class="h">Chuva</span><span>Open-Meteo, previsão hora a hora</span></div>
          <div><span class="h">Cidade</span><span>OpenStreetMap e GeoSampa: semáforos e escolas</span></div>
          <div><span class="h">Câmera</span><span>vídeos públicos (Pexels) e clipes gerados por IA para testes</span></div>
          <div><span class="h">Trânsito</span><span>simulação no SUMO de um cruzamento com as medidas do piloto</span></div>
        </div>"""
    html('<div class="bw-grade">'
         + es.superficie("pino", "O piloto: Largo da Concórdia, no Brás", f"<p>{es.esc(piloto)}</p>")
         + es.superficie("cadeado", "Privacidade", "<p>Nenhum rosto é reconhecido. Rostos e placas saem borrados antes "
                         "de qualquer imagem ser mostrada, e o sistema guarda só números e horários. Cada vez que "
                         "alguém abre uma câmera, o acesso fica registrado com nome e horário.</p>")
         + es.superficie("dados", "De onde vêm os dados", dados)
         + es.superficie("info", "Limites", "<p>Os ganhos no trânsito são resultados esperados de simulação. Só o Largo "
                         "da Concórdia tem câmera instalada; as outras câmeras da rede são simuladas. A ambulância "
                         "despachada é simulada e não há integração com a CET ou o SAMU.</p>")
         + "</div>")
    with st.container(key="sup_clipes"):
        _clipes_sinteticos()
    html('<p class="bw-nota" style="margin-top:12px">Global Solution FIAP 2026.2 · Tamires Vitória Ferreira dos Santos, '
         'turma 1TIAO.</p>')


# ---------------------------------------------------------------- painel (gestão)
def _cartao_leitura(l: lt.Leitura, quando: datetime, simulado: bool) -> str:
    linhas = ""
    for e in l.evidencias:
        ic, cor = es.ICONE_EVIDENCIA[e.estado]
        linhas += (f'<div class="bw-ev">{es.icone(ic, cor, 20)}<span class="nome">{es.esc(e.nome)}</span>'
                   f'<span class="txt">{es.esc(e.texto)}</span><span class="fonte">{es.esc(e.fonte)}</span></div>')
    quando_txt = f"{DIAS[quando.weekday()]}, {quando:%H:%M}" + (" · horário simulado" if simulado else "")
    return (f'<div class="bw-leitura {l.nivel}"><div class="topo">{es.selo_nivel(l.nivel)}'
            f'<span class="bw-nota">Leitura da situação · {es.esc(quando_txt)}</span></div>'
            f'<div class="titulo" style="margin:10px 0 6px">{es.esc(l.titulo)}</div>{linhas}'
            f'<div class="bw-conclusao"><b>O que fazer:</b> {es.esc(l.recomendacao)}</div></div>')


def pagina_painel() -> None:
    st.title("Painel do ponto crítico")
    st.caption("Largo da Concórdia, Brás. A leitura junta histórico, chuva, câmera e modelo, e é refeita a cada minuto.")
    with st.expander("Simular um horário (para apresentar a leitura)"):
        st.caption("Escolha um dia, uma hora e a chuva para ver como a leitura muda. Só a leitura muda: o histórico, a "
                   "câmera e o modelo continuam os mesmos, e a linha do tempo marca a leitura como simulada.")
        sim = st.toggle("Usar horário simulado", key="sim_on")
        a, b, c = st.columns(3)
        dia = a.selectbox("Dia", DIAS, index=1, key="sim_dia")
        hora = b.time_input("Hora", time(17, 40), key="sim_hora")
        chuva_sim = c.number_input("Chuva (mm/h)", 0.0, 50.0, 5.0, 0.5, key="sim_chuva")
    agora = datetime.now(m.FUSO).replace(tzinfo=None)
    if sim:
        base = agora - timedelta(days=agora.weekday()) + timedelta(days=DIAS.index(dia))
        quando, chuva = base.replace(hour=hora.hour, minute=hora.minute, second=0, microsecond=0), chuva_sim
    else:
        quando, chuva = agora, chuva_agora()
    leit = _calcular_leitura(quando, chuva, agora)
    rk = risco_em(quando.replace(second=0, microsecond=0).isoformat(), chuva or 0.0)
    lt.registrar(conexao(), leit, quando, simulado=sim)
    html(_cartao_leitura(leit, quando, sim))
    if leit.nivel != "normal":
        html('<div class="bw-grid">'
             f'<div class="bw-card"><span class="icone">{es.icone("pedestre")}</span><h3>Mais tempo na faixa</h3>'
             '<p>O verde do pedestre se estende para quem ainda está atravessando.</p></div>'
             f'<div class="bw-card"><span class="icone">{es.icone("escudo")}</span><h3>Avenida espera a faixa vazia</h3>'
             '<p>Os carros só recebem o verde quando não há ninguém na faixa.</p></div>'
             f'<div class="bw-card"><span class="icone">{es.icone("alerta")}</span><h3>Aviso aos motoristas</h3>'
             '<p>O painel de LED do nó avisa que há gente atravessando.</p></div></div>')

    no = no_ao_vivo()
    abertas = oc.listar(conexao(), ["pendente", "confirmada", "despachada"])
    tempos = _tempos_ocorrencias()
    conf = tempos["Até confirmar (s)"].dropna() if not tempos.empty else pd.Series(dtype=float)
    k = st.columns(4)
    with k[0]:
        html(es.kpi("Modo do semáforo", cam.NOMES_MODO.get((no.estado or {}).get("modo"), "Sem sinal do nó"),
                    "nó ESP32 na faixa"))
    with k[1]:
        html(es.kpi("Risco agora", f"{rk['risco_relativo']:.1f}×".replace(".", ",") if rk else "Sem dados",
                    "a média da cidade"))
    with k[2]:
        html(es.kpi("Ocorrências em aberto", str(len(abertas)), "aguardando validação ou atendimento"))
    with k[3]:
        html(es.kpi("Tempo até confirmar", f"{conf.mean():.0f} s" if len(conf) else "Sem dados", "média das ocorrências"))
    st.write("")
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        with cartao("risco_ao_longo_do_dia_no_largo", "grafico", "Risco ao longo do dia no Largo"):
            _curva_risco(quando)
    with c2:
        with cartao("linha_do_tempo_das_leituras", "relogio", "Linha do tempo das leituras"):
            hist_l = lt.historico(conexao(), 8)
            if not hist_l:
                st.caption("A primeira leitura aparece aqui.")
            linhas = "".join(
                f'<div><span class="h">{datetime.fromisoformat(r["timestamp"]):%H:%M}</span><span>'
                f'{es.selo_nivel(r["nivel"])}{" <span class=bw-nota>simulada</span>" if r["simulado"] else ""}'
                f'<br><span class="bw-nota">{es.esc(r["resumo"].split(" · ")[0])}</span></span></div>' for r in hist_l)
            html(f'<div class="bw-tempo">{linhas}</div>')
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        with cartao("mapa_de_risco_da_cidade", "pino", "Mapa de risco da cidade"):
            _mapa()
    with c2:
        with cartao("os_pontos_mais_criticos", "alerta", "Os pontos mais críticos"):
            top = consultar("SELECT cluster_id, rank_urbano, via_principal, n_fatais, n_nao_fatais FROM clusters "
                            "WHERE rank_urbano IS NOT NULL AND (rank_urbano <= 9 OR cluster_id = ?) ORDER BY rank_urbano",
                            (PILOTO,))
            html(cp.ranking_pontos([{"rank_urbano": int(r.rank_urbano),
                                     "via": "Largo da Concórdia" if r.cluster_id == PILOTO else cam.nome_de_via(r.via_principal),
                                     "atropelamentos": int(r.n_fatais + r.n_nao_fatais), "mortes": int(r.n_fatais),
                                     "piloto": r.cluster_id == PILOTO}
                                    for r in top.itertuples()]))
            html('<p class="bw-nota">O número é o total de atropelamentos do ponto (Infosiga-SP, 2022 a 2025). A posição segue '
                 'o índice de prioridade da CET (Companhia de Engenharia de Tráfego): cada morte pesa 3 vezes e o total é '
                 'dividido pelo tamanho do trecho. Por isso um ponto curto com mortes pode vir antes de um com mais '
                 'atropelamentos espalhados.</p>')


def _curva_risco(quando: datetime) -> None:
    """Risco do piloto hora a hora (modelo do notebook 06), com o horário da leitura marcado."""
    import altair as alt
    dia = quando.replace(minute=30, second=0, microsecond=0)
    pontos = [{"hora": h, "risco": r["risco_relativo"]} for h in range(24)
              if (r := risco_em(dia.replace(hour=h).isoformat(), 0.0))]
    if not pontos:
        st.caption("Modelo de risco indisponível.")
        return
    df = pd.DataFrame(pontos)
    df["rotulo"] = df["hora"].map(lambda h: f"{h:02d}h")
    t = tema()
    c_texto, c_muted, c_borda = es.cor("texto", t), es.cor("muted", t), es.cor("borda", t)
    base = alt.Chart(df).encode(x=alt.X("hora:Q", title=None, scale=alt.Scale(domain=[0, 23]),
                                        axis=alt.Axis(values=list(range(0, 24, 3)), labelExpr="datum.value + 'h'")))
    area = base.mark_area(color=es.VERDE, opacity=0.14, interpolate="monotone").encode(y="risco:Q")
    linha = base.mark_line(color=es.VERDE, strokeWidth=2, interpolate="monotone").encode(
        y=alt.Y("risco:Q", title="vezes a média da cidade", axis=alt.Axis(tickCount=4)))
    pontos_ = base.mark_circle(size=90, opacity=0).encode(
        y="risco:Q", tooltip=[alt.Tooltip("rotulo:N", title="Hora"),
                              alt.Tooltip("risco:Q", title="Risco (× cidade)", format=".1f")])
    agora = alt.Chart(pd.DataFrame({"hora": [quando.hour + quando.minute / 60], "t": ["agora"]})).mark_rule(
        color=c_texto, strokeDash=[4, 4]).encode(x="hora:Q")
    rotulo = alt.Chart(pd.DataFrame({"hora": [quando.hour + quando.minute / 60], "t": [f"{quando:%H:%M}"]})).mark_text(
        color=c_texto, dy=-8, align="left", dx=6, fontSize=14, font="Montserrat").encode(x="hora:Q", y=alt.value(12),
                                                                                         text="t:N")
    graf = (area + linha + pontos_ + agora + rotulo).properties(height=260).configure(
        background="transparent", font="Montserrat").configure_axis(
        labelColor=c_muted, titleColor=c_muted, gridColor=c_borda, domainColor=c_borda, labelFontSize=13,
        titleFontSize=13, tickColor=c_borda).configure_view(strokeWidth=0)
    st.altair_chart(graf, width="stretch")
    pico = df.loc[df.risco.idxmax()]
    vezes = f"{pico.risco:.1f}".replace(".", ",")
    html(f'<p class="bw-nota">Dia útil, sem chuva. O pico é por volta das {int(pico.hora)}h ({vezes}× a média da '
         f'cidade). A linha tracejada marca o horário da leitura.</p>')


def _mapa() -> None:
    import pydeck as pdk
    cl = consultar("SELECT * FROM clusters WHERE rank_urbano IS NOT NULL")
    if cl.empty:
        st.info("Sem pontos críticos no banco. Gere-os com os notebooks 03 e 04.")
        return
    cl = cl.assign(raio=(cl["peso"].clip(lower=1) ** 0.5) * 80, via=cl["via_principal"].fillna("Via sem nome"))
    corte = cl["rank_urbano"]
    cl["cor"] = [[230, 57, 70, 220] if r <= 20 else [255, 176, 0, 200] if r <= 60 else [0, 194, 122, 150]
                 for r in corte]
    cl["faixa"] = ["entre os 20 mais críticos" if r <= 20 else "do 21º ao 60º" if r <= 60 else "demais pontos"
                   for r in corte]
    piloto = cl[cl.cluster_id == PILOTO]
    st.pydeck_chart(pdk.Deck(
        map_style="dark",
        layers=[pdk.Layer("ScatterplotLayer", cl, get_position="[lon_centro, lat_centro]", get_radius="raio",
                          get_fill_color="cor", pickable=True, radius_min_pixels=3),
                pdk.Layer("ScatterplotLayer", piloto, get_position="[lon_centro, lat_centro]", get_radius=300,
                          filled=False, stroked=True, get_line_color=[244, 244, 239], line_width_min_pixels=3)],
        initial_view_state=pdk.ViewState(latitude=-23.56, longitude=-46.63, zoom=10.2),
        tooltip={"text": "{via}\n{rank_urbano}º do ranking urbano\n{n_nao_fatais} atropelamentos sem morte, "
                         "{n_fatais} com morte"}), height=420)
    html('<p class="bw-nota">Cada ponto é um grupo de atropelamentos (Infosiga-SP, 2022 a 2025). Vermelho: entre os 20 '
         'mais críticos; âmbar: do 21º ao 60º; verde: demais. O anel claro marca o piloto. Toque num ponto para ver '
         'a via.</p>')


# ---------------------------------------------------------------- ocorrências (gestão)
NOMES_ESTADO = {"pendente": "Aguardando o Trânsito", "confirmada": "Confirmada, aguardando a Saúde",
                "descartada": "Descartada", "despachada": "Atendimento a caminho", "encerrada": "Encerrada"}


def _tempos_ocorrencias() -> pd.DataFrame:
    linhas, con = [], conexao()
    for o in oc.listar(con):
        t = oc.tempos(con, o["id"])

        def seg(a, b):
            if a in t and b in t:
                return (datetime.fromisoformat(t[b]["timestamp"]) - datetime.fromisoformat(t[a]["timestamp"])).total_seconds()
            return None
        linhas.append({"Nº": o["id"], "O que": oc.TIPOS.get(o["tipo"], o["tipo"]),
                       "Quem abriu": "Câmera" if o["origem"] == "visao" else "Operador(a)",
                       "Situação": NOMES_ESTADO.get(o["estado"], o["estado"]),
                       "Aberta em": datetime.fromisoformat(o["aberta_em"]).strftime("%d/%m %H:%M"),
                       "Até confirmar (s)": seg("pendente", "confirmada"),
                       "Até despachar (s)": seg("confirmada", "despachada"),
                       "Atendimento (s)": seg("despachada", "encerrada"),
                       "Motivo do descarte": (t.get("descartada") or {}).get("motivo")})
    return pd.DataFrame(linhas)


def _linhas_quadro() -> list[dict]:
    con, linhas = conexao(), []
    for o in oc.listar(con):
        t = oc.tempos(con, o["id"])

        def seg(a, b):
            if a in t and b in t:
                return (datetime.fromisoformat(t[b]["timestamp"]) - datetime.fromisoformat(t[a]["timestamp"])).total_seconds()
            return None
        linhas.append({"id": o["id"], "tipo": oc.TIPOS.get(o["tipo"], o["tipo"]), "origem": o["origem"],
                       "estado": o["estado"], "aberta": datetime.fromisoformat(o["aberta_em"]).strftime("%d/%m %H:%M"),
                       "confirmar": seg("pendente", "confirmada"), "despachar": seg("confirmada", "despachada"),
                       "atender": seg("despachada", "encerrada"), "motivo": (t.get("descartada") or {}).get("motivo")})
    return linhas


def pagina_ocorrencias_gestao() -> None:
    st.title("Ocorrências")
    st.caption("Cada suspeita de acidente passa pelo Trânsito, que confirma ou descarta, e pela Saúde, que despacha o "
               "atendimento. Cada cartão mostra quanto tempo cada etapa levou.")
    linhas = _linhas_quadro()
    if not linhas:
        st.info("Nenhuma ocorrência registrada ainda. Quando a câmera ou um operador abrir uma, ela aparece aqui.")
        return
    media = lambda k: [o[k] for o in linhas if o[k] is not None]  # noqa: E731
    k = st.columns(4)
    with k[0]:
        html(es.kpi("Em aberto", str(sum(o["estado"] in ("pendente", "confirmada", "despachada") for o in linhas)),
                    "aguardando alguém agir"))
    with k[1]:
        c = media("confirmar")
        html(es.kpi("Até confirmar", f"{sum(c) / len(c):.0f} s" if c else "Sem dados", "média do Trânsito"))
    with k[2]:
        d = media("despachar")
        html(es.kpi("Até despachar", f"{sum(d) / len(d):.0f} s" if d else "Sem dados", "média da Saúde"))
    with k[3]:
        html(es.kpi("Descartadas", str(sum(o["estado"] == "descartada" for o in linhas)), "falsos alarmes"))
    st.write("")
    html(cp.quadro_ocorrencias(linhas))
    con = conexao()
    ct.migrar(con)
    leituras = ct.recentes(con, 10)
    with cartao("travessias_extra", "pedestre", "Travessias com tempo extra"):
        if not leituras:
            st.caption("Nenhuma ainda. Cada cartão lido ou pedido da câmera aparece aqui.")
        else:
            html('<div class="bw-tempo">' + "".join(
                f'<div><span class="h">{datetime.fromisoformat(r["timestamp"]):%d/%m %H:%M}</span><span>'
                f'{es.esc(ct.ORIGENS[r["origem"]])}: {es.esc(ct.TIPOS.get(r["tipo"], "pessoa com auxílio de mobilidade"))}'
                f' · {es.esc(r["faixa"])} · +{r["extra_s"]:.1f} s'.replace(".", ",")
                + (' <span class="bw-sim">simulado</span>' if r["simulado"] else "") + '</span></div>'
                for r in leituras) + '</div>')


# ---------------------------------------------------------------- resultados da simulação
def _barras(rotulo: str, sem: float, com: float, unidade: str, menor_melhor: bool = True) -> str:
    topo = max(sem, com) or 1
    melhor = (com < sem) if menor_melhor else (com > sem)
    var = (com - sem) / sem * 100 if sem else 0
    cor_var = es.VERDE if melhor else es.ALERTA_INK
    fmt = lambda v: f"{v:.1f}".replace(".", ",")  # noqa: E731
    return (f'<div class="bw-card"><div class="r" style="color:{es.MUTED};font-size:13px;font-weight:500">'
            f'{es.esc(rotulo)}</div>'
            f'<div style="display:grid;grid-template-columns:86px 1fr 64px;gap:8px;align-items:center;margin-top:12px">'
            f'<span class="bw-nota">Hoje</span><div style="height:12px;border-radius:6px;background:var(--bw-trilho);'
            f'width:{sem / topo * 100:.0f}%"></div><b style="text-align:right">{fmt(sem)} {unidade}</b>'
            f'<span class="bw-nota">BetterWay</span><div style="height:12px;border-radius:6px;background:{es.VERDE};'
            f'width:{com / topo * 100:.0f}%"></div><b style="text-align:right">{fmt(com)} {unidade}</b></div>'
            f'<div style="margin-top:10px;font-weight:700;color:{cor_var}">{"−" if var < 0 else "+"}'
            f'{abs(var):.0f}%</div></div>')


def _br(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def _barras_sistema() -> None:
    """Hoje × BetterWay com tudo ligado junto (rodadas de 30 min do Estudo A)."""
    p = EVID / "estudo_a" / "estudo_a_resumo.csv"
    if not p.exists():
        return
    r = pd.read_csv(p, sep=";", encoding="utf-8-sig").set_index(["comparacao", "sistema"])
    s, c = r.loc[("completo", "sem")], r.loc[("completo", "com")]
    so = r.loc[("semaforo", "com")]
    risco_s = s.na_faixa_carros_verde_reduzida + s.na_faixa_carros_verde_comum
    risco_c = c.na_faixa_carros_verde_reduzida + c.na_faixa_carros_verde_comum
    html('<div class="bw-secao" style="margin-top:20px">Tudo ligado junto: hoje e com a BetterWay</div>')
    html('<div class="bw-grid">' +
         _barras("Pessoas na faixa com os carros em verde (por rodada)", risco_s, risco_c, "") +
         _barras("Espera de quem atravessa", s.espera_media_pedestre_s, c.espera_media_pedestre_s, "s") +
         _barras("Tempo da ambulância", s.tempo_ambulancia_s, c.tempo_ambulancia_s, "s") +
         _barras("Atraso médio de cada carro", s.atraso_medio_carro_s, c.atraso_medio_carro_s, "s") +
         '</div>')
    html(f'<p class="bw-nota">Média de 5 rodadas de 30 minutos simulados no SUMO; resultado esperado de simulação. '
         f'Segurança primeiro: o semáforo só troca o verde depois de 4 s sem carro chegando, sempre com amarelo e '
         f'vermelho total, e nunca solta os carros com gente na faixa. O custo é de cerca de '
         f'{_br(abs(c.atraso_medio_carro_s - s.atraso_medio_carro_s))} s a mais por carro. Um semáforo que só reage aos '
         f'carros andaria mais rápido ({_br(so.atraso_medio_carro_s)} s), mas soltaria os carros com gente na faixa.</p>')


def _clipes_sinteticos() -> None:
    html('<div class="bw-secao" style="margin-top:12px">Como testamos a câmera</div>')
    st.caption("Clipes curtos gerados por IA (Veo 3), cada um com o resultado esperado. Mostram a regra funcionando; "
               "não medem desempenho na rua, por isso ficam separados dos resultados com vídeo real.")
    p = EVID / "operador" / "avaliacao_clipes.csv"
    if not p.exists():
        st.info("Os clipes ainda estão sendo gerados. Quando forem processados, o resultado de cada um aparece aqui.")
        return
    df = pd.read_csv(p, sep=";", encoding="utf-8-sig")
    html(es.kpi("Clipes com o resultado esperado", f"{int(df.acerto.sum())} de {len(df)}", "avaliação sintética"))
    st.write("")
    html(cp.cartoes_clipes(df.to_dict("records")))


# ---------------------------------------------------------------- sala de controle
def pagina_sala() -> None:
    u = st.session_state["usuario"]
    st.title("Sala de controle")
    st.caption("O nó da faixa do Largo da Concórdia ao vivo: o que o semáforo está fazendo agora e o que ele relatou.")
    with st.expander("Como funciona a sala de controle"):
        html("""<div class="bw-tempo">
          <div><span class="h">Nó</span><span>A caixa ligada ao semáforo da faixa (um ESP32). Ela recebe as ordens da
            central e manda de volta o que está fazendo.</span></div>
          <div><span class="h">Modo</span><span>O jeito de operar agora: normal, pedestre, escola, chuva ou
            ambulância. A central escolhe sozinha pelo horário, pela chuva e pela câmera.</span></div>
          <div><span class="h">Semáforo</span><span>O desenho mostra a luz acesa agora para os carros e para o
            pedestre, escrita ao lado.</span></div>
          <div><span class="h">Sinais</span><span>Tudo o que o nó fez, em ordem: cartão lido, câmera pedindo
            mais tempo para quem tem andador ou cadeira de rodas, verde estendido, ambulância chegando. O tempo extra
            é automático: ninguém precisa liberar.</span></div>
          <div><span class="h">Quem muda</span><span>Só a equipe de Trânsito pode trocar o modo à mão. Gestão e Saúde
            acompanham.</span></div></div>""")
    no = no_ao_vivo()

    @st.fragment(run_every=3)
    def estado():
        e = no.estado or {}
        c1, c2 = st.columns([3, 2], gap="large")
        with c1:
            with cartao("semaforo_agora", "semaforo", "O semáforo agora"):
                html(cp.semaforo_svg(e.get("fase")))
            st.write("")
            k = st.columns(2)
            with k[0]:
                html(es.kpi("Modo", cam.NOMES_MODO.get(e.get("modo"), "Sem sinal"),
                            f"atualizado às {no.estado_recebido_em:%H:%M:%S}" if no.estado_recebido_em else
                            "o nó ainda não respondeu"))
            with k[1]:
                html(es.kpi("Conexão", "Conectada à central" if no.conectado else "Sem conexão com a central", "",
                            estado="ok" if no.conectado else "alerta"))
        with c2:
            with cartao("sinais_do_no", "sinal", "Sinais do nó"):
                _sinais(list(no.eventos))
    estado()
    _simular_sinal(no)
    st.write("")
    if pode(u.perfil, "cenario"):
        with cartao("mudar_o_modo_do_semaforo", "semaforo", "Mudar o modo do semáforo"):
            st.caption("Envia o comando direto ao nó. Não use ao mesmo tempo que a central automática.")
            cols = st.columns(3)
            for i, nome in enumerate(CENARIOS):
                if cols[i % 3].button(ROTULOS_CENARIO[nome], key=f"cen_{nome}", width="stretch"):
                    try:
                        exigir(u.perfil, "cenario")
                        ok = no.publicar(comando_cenario(nome))
                        st.toast(f"Modo {ROTULOS_CENARIO[nome]}: {'enviado' if ok else 'não enviado, sem conexão'}")
                    except SemPermissao as erro:
                        st.error(str(erro))
    else:
        st.caption("Só a equipe de Trânsito muda o modo do semáforo.")


def _sinais(eventos: list[dict]) -> None:
    """Registro automático do que o nó fez. Cartão e câmera pedem o tempo extra sozinhos: ninguém precisa liberar."""
    if not eventos:
        html(cp.feed_eventos([]))
        return
    html(cp.feed_eventos(eventos, limite=8))


SIMULAVEIS = {"cartao_lido": "Cartão encostado no leitor", "camera_pediu_tempo": "Câmera viu alguém com andador",
              "pedido_atendido_apos_ambulancia": "Pedido atendido depois da ambulância"}


def _enviar_simulado(no) -> None:
    """Roda no clique, antes de a página ser montada: o sinal já aparece no registro desta mesma atualização."""
    seq = st.session_state.get("sim_seq", 0) + 1
    st.session_state["sim_seq"] = seq
    base = int(time_mod.time()) * 100 + seq * 2
    tipo = st.session_state.get("sim_tipo", "cartao_lido")
    for k, t in enumerate([tipo] + (["travessia_estendida"] if tipo in ("cartao_lido", "camera_pediu_tempo") else [])):
        no.receber(m.TOPICO_EVENTO, json.dumps(sn.evento_simulado(t, base + k)).encode())
    st.toast("Sinal simulado enviado ao registro")


def _simular_sinal(no) -> None:
    """Plano B da demonstração: o mesmo evento que o ESP32 mandaria, marcado como simulado."""
    with st.expander("Demonstração sem o ESP32: simular um sinal do nó"):
        st.caption("Use se o Wokwi estiver fora do ar ou sem rede. O sinal entra no registro como se viesse do nó, "
                   "com o selo simulado.")
        st.selectbox("Sinal", list(SIMULAVEIS), format_func=SIMULAVEIS.get, key="sim_tipo")
        st.button("Simular sinal do nó", key="sim_enviar", on_click=_enviar_simulado, args=(no,))


# ---------------------------------------------------------------- central de demonstrações
def _ler_cartao(no) -> None:
    con = conexao()
    ct.migrar(con)
    origem = st.session_state.get("demo_origem", "cartao")
    r = ct.registrar(con, origem=origem, tipo=st.session_state.get("demo_tipo", "idoso"), simulado=True)
    base = int(time_mod.time()) * 100
    for k, t in enumerate(["cartao_lido" if origem == "cartao" else "camera_pediu_tempo", "travessia_estendida"]):
        no.receber(m.TOPICO_EVENTO, json.dumps(sn.evento_simulado(t, base + k)).encode())
    st.session_state["demo_ultima"] = r


def _avisar_motoristas() -> None:
    st.session_state["demo_sms"] = datetime.now(m.FUSO).strftime("%H:%M")


def _html_leitor(ultima: dict | None) -> str:
    if ultima is None:
        tela = '<b>Encoste o cartão</b><span>Bilhete Único Idoso ou Especial</span>'
        classe = ""
    else:
        quem = ct.TIPOS.get(ultima["tipo"], "Câmera: pessoa com andador")
        tela = (f'<b>Tempo extra concedido</b><span>{es.esc(quem)}</span>'
                f'<span class="num">+{ultima["extra_s"]:.1f} s</span>'.replace(".", ",", 1))
        classe = " lido"
    return (f'<div class="bw-leitor{classe}"><div class="poste"><div class="caixa">'
            f'<span class="nfc">{es.icone("sinal", "#F5F5F2", 28)}</span><div class="tela">{tela}</div></div></div></div>')


def _html_celular(hora: str | None, via: str) -> str:
    aviso = ""
    if hora:
        aviso = (f'<div class="aviso"><div class="cab"><span class="app">Alerta de emergência</span>'
                 f'<span>{es.esc(hora)}</span></div><p>{es.esc(ct.mensagem_sms(via))}</p></div>')
    return (f'<div class="bw-cel"><div class="tela"><div class="barra"><span>{datetime.now(m.FUSO):%H:%M}</span>'
            f'<span>5G</span></div><div class="relogio">{datetime.now(m.FUSO):%H:%M}</div>{aviso}</div></div>')


def pagina_demonstracoes() -> None:
    st.title("Central de demonstrações")
    st.caption("Mostra, sem o equipamento de rua, como a pessoa e o motorista veem a BetterWay. Tudo aqui é "
               "simulado e fica marcado como simulado.")
    no = no_ao_vivo()
    c1, c2 = st.columns(2, gap="large")
    with c1, cartao("demo_cartao", "pedestre", "Cartão na faixa"):
        html('<p class="bw-nota" style="margin:0 0 16px">Quem precisa de mais tempo encosta o Bilhete Único no leitor '
             'do poste, como no Green Man+ de Singapura. Esqueceu o cartão? A câmera percebe o andador ou a cadeira '
             'de rodas e pede o tempo sozinha.</p>')
        v, ctrl = st.columns([1, 1], gap="medium", vertical_alignment="center")
        with v:
            html(_html_leitor(st.session_state.get("demo_ultima")))
        with ctrl:
            st.radio("Quem pede o tempo", ["cartao", "camera"], key="demo_origem", horizontal=True,
                     format_func={"cartao": "Cartão", "camera": "Câmera"}.get)
            if st.session_state.get("demo_origem", "cartao") == "cartao":
                st.selectbox("Cartão", list(ct.TIPOS), format_func=ct.TIPOS.get, key="demo_tipo")
            st.button("Encostar o cartão" if st.session_state.get("demo_origem", "cartao") == "cartao"
                      else "Câmera vê a pessoa com andador", type="primary", key="demo_ler",
                      on_click=_ler_cartao, args=(no,), width="stretch")
        con = conexao()
        ct.migrar(con)
        linhas = ct.recentes(con, 6)
        if linhas:
            html('<div class="bw-tempo" style="margin-top:16px">' + "".join(
                f'<div><span class="h">{datetime.fromisoformat(r["timestamp"]):%H:%M:%S}</span><span>'
                f'{es.esc(ct.TIPOS.get(r["tipo"], "Câmera: pessoa com auxílio de mobilidade"))} · '
                f'+{r["extra_s"]:.1f} s'.replace(".", ",") + (' <span class="bw-sim">simulado</span>' if r["simulado"] else "")
                + '</span></div>' for r in linhas) + '</div>')
        html('<p class="bw-nota" style="margin-top:12px">Fica registrado só o tipo de cartão, o horário e o tempo '
             'extra. Nenhum número de cartão nem nome.</p>')
    with c2, cartao("demo_celular", "ambulancia", "Alerta no celular do motorista"):
        html('<p class="bw-nota" style="margin:0 0 16px">Quando a ambulância está a 1 km, os celulares no trecho à '
             'frente dela recebem um alerta por área, como os da Defesa Civil. Ninguém precisa dar o número.</p>')
        v, ctrl = st.columns([1, 1], gap="medium", vertical_alignment="center")
        with v:
            html(_html_celular(st.session_state.get("demo_sms"), "Avenida Rangel Pestana"))
        with ctrl:
            st.button("Ambulância a 1 km", type="primary", key="demo_sms_btn", on_click=_avisar_motoristas,
                      width="stretch")
            if st.session_state.get("demo_sms"):
                st.button("Limpar o celular", key="demo_sms_limpar",
                          on_click=lambda: st.session_state.pop("demo_sms", None), width="stretch")
            html('<p class="bw-nota" style="margin-top:12px">Na rua, o envio seria por alerta de celular da região '
                 '(cell broadcast) a partir da central. Aqui é só a demonstração da mensagem.</p>')


# ---------------------------------------------------------------- câmeras
@st.cache_data(show_spinner=False)
def clipes_da_rede() -> list[cam.Clipe]:
    if os.environ.get("BETTERWAY_SEM_CLIPES"):
        return []
    todos = cam.clipes_disponiveis(incluir_reais=True)
    novos = [c for nome in CLIPES_REDE for c in todos if c.nome == nome]
    return novos or todos


def _abrir_camera(cam_id: str | None) -> None:
    st.session_state["cam_aberta"] = cam_id


def _chave(cam_id: str) -> str:
    return cam_id.replace(" ", "_")


def _nome_de(usuario: str | None) -> str:
    if not usuario:
        return ""
    linha = conexao().execute("SELECT nome FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
    return f"{linha[0]} ({usuario})" if linha else usuario


def _hora(ts: str | None) -> str:
    return datetime.fromisoformat(ts).strftime("%d/%m %H:%M:%S") if ts else ""


def pagina_cameras() -> None:
    u = st.session_state["usuario"]
    pontos = consultar("SELECT cluster_id, rank_urbano, via_principal FROM clusters WHERE rank_urbano IS NOT NULL "
                       "AND (rank_urbano <= 12 OR cluster_id = ?) ORDER BY rank_urbano", (PILOTO,)).to_dict("records")
    clipes_rede = clipes_da_rede()
    rede = cam.rede_de_cameras(pontos, clipes_rede, piloto=PILOTO, n=min(6, len(clipes_rede)) or 6,
                               clipe_piloto=CLIPE_PILOTO)
    urls = {c.id: cam.url_estatica(c.clipe) for c in rede}
    aberta = next((c for c in rede if c.id == st.session_state.get("cam_aberta")), None)
    if aberta is not None:
        _camera_aberta(aberta, urls[aberta.id], u)
        _faixa_cameras(rede, urls, aberta.id)
        return
    st.title("Câmeras")
    st.caption("Todas as câmeras da rede BetterWay, ao vivo. Clique numa câmera para acompanhar de perto e registrar "
               "uma ocorrência.")
    por_linha = 5
    for ini in range(0, len(rede), por_linha):
        cols = st.columns(por_linha, gap="small")
        for col, c in zip(cols, rede[ini:ini + por_linha]):
            with col, st.container(key=f"camcard_{_chave(c.id)}"):
                html(cam.html_cartao(c, urls.get(c.id)))
                st.button(f"Abrir {c.id}", key=f"abrir_{_chave(c.id)}", on_click=_abrir_camera, args=(c.id,))
    _relatorios_enviados()
    if u.perfil == "gestao":
        con = conexao()
        cam.migrar(con)
        ac = pd.read_sql_query("SELECT timestamp, usuario, camera FROM acessos_camera ORDER BY id DESC LIMIT 10", con)
        with cartao("quem_abriu_as_cameras", "camera", "Quem abriu as câmeras"):
            html(cp.lista_acessos([{"usuario": r.usuario, "camera": r.camera,
                                    "quando": pd.to_datetime(r.timestamp).strftime("%d/%m %H:%M")} for r in ac.itertuples()]))


def _mover_faixa(passo: int, total: int) -> None:
    st.session_state["cam_faixa_ini"] = max(0, min(total - 1, st.session_state.get("cam_faixa_ini", 0) + passo))


def _faixa_cameras(rede, urls, atual: str, por_vez: int = 4) -> None:
    """As outras câmeras em miniatura, embaixo da principal: troca de câmera sem voltar ao mosaico."""
    outras = [c for c in rede if c.id != atual]
    if not outras:
        return
    ini = min(st.session_state.get("cam_faixa_ini", 0), max(0, len(outras) - por_vez))
    with cartao("outras_cameras", "camera", "Outras câmeras"):
        esq, meio, dir_ = st.columns([1, 20, 1], vertical_alignment="center")
        with esq:
            st.button("Câmeras anteriores", key="faixa_esq", disabled=ini == 0, on_click=_mover_faixa,
                      args=(-1, len(outras)))
        with meio:
            cols = st.columns(por_vez, gap="small")
            for col, c in zip(cols, outras[ini:ini + por_vez]):
                with col, st.container(key=f"camcard_mini_{_chave(c.id)}"):
                    html(cam.html_cartao(c, urls.get(c.id)))
                    st.button(f"Abrir {c.id}", key=f"abrir_mini_{_chave(c.id)}", on_click=_abrir_camera, args=(c.id,))
        with dir_:
            st.button("Próximas câmeras", key="faixa_dir", disabled=ini + por_vez >= len(outras), on_click=_mover_faixa,
                      args=(1, len(outras)))


def _camera_aberta(c, url: str | None, u) -> None:
    st.button("Voltar às câmeras", key="cam_voltar", on_click=_abrir_camera,
              args=(None,))
    st.title(f"{c.id} · {c.local}")
    if st.session_state.get("cam_registrada") != c.id:
        con = conexao()
        cam.migrar(con)
        cam.registrar_visualizacao(con, u.usuario, c.id)
        st.session_state["cam_registrada"] = c.id
    esq, dir_ = st.columns([3, 2], gap="large")
    with esq:
        if c.clipe is None or url is None:
            st.info("Esta câmera está sem vídeo agora.")
        else:
            modo = (no_ao_vivo().estado or {}).get("modo") if c.instalada else None
            components.html(cam.html_player(c.clipe, modo, video_url=url, camera=f"{c.id} · {c.local}"), height=560)
        origem = ("Câmera instalada com o nó da faixa." if c.instalada else
                  "Câmera simulada: vídeo de referência num ponto crítico do ranking.")
        html(f'<p class="bw-nota">{origem} Seu acesso a esta câmera foi registrado.</p>')
    with dir_:
        _form_registro(c, u)


def _guardar(chave: str) -> None:
    """Copia o valor do campo para fora do widget: o rascunho sobrevive a sair da câmera e voltar."""
    st.session_state["_rasc_" + chave] = st.session_state[chave]


def _restaurar(*chaves: str) -> None:
    for k in chaves:
        if k not in st.session_state and "_rasc_" + k in st.session_state:
            st.session_state[k] = st.session_state["_rasc_" + k]


def _form_registro(c, u) -> None:
    with cartao("registrar_ocorrencia", "editar", "Registrar ocorrência"):
        if st.session_state.get("aviso_registro"):
            st.success(st.session_state.pop("aviso_registro"))
        con = conexao()
        rg.migrar(con)
        chave = f"registro_{_chave(c.id)}"
        rid = st.session_state.get(chave)
        if rid is None:
            st.caption("Viu algo nesta câmera? Descreva o que aconteceu, anexe quadros do vídeo e acione quem precisa ir.")
            if st.button("Começar registro", type="primary", key="reg_comecar"):
                try:
                    st.session_state[chave] = rg.iniciar(con, usuario=u, camera=c.id, local=c.local,
                                                         cluster_id=c.cluster_id,
                                                         video_id=f"veo3_{c.clipe.nome}" if c.clipe else None)
                    st.rerun()
                except SemPermissao as erro:
                    st.error(str(erro))
            return
        r = rg.obter(con, rid)
        html(f'<p class="bw-nota">Relatório Nº {rid} · registrado por {es.esc(_nome_de(r["registrado_por"]))} em '
             f'{_hora(r["registrado_em"])}</p>')
        _restaurar(f"reg_sit_{rid}", f"reg_desc_{rid}", f"reg_seg_{rid}", *(f"reg_ac_{a}_{rid}" for a in rg.ACIONAMENTOS))
        situacao = st.selectbox("O que aconteceu", list(rg.SITUACOES), format_func=rg.SITUACOES.get, index=None,
                                placeholder="Escolha o tipo de situação", key=f"reg_sit_{rid}", on_change=_guardar,
                                args=(f"reg_sit_{rid}",))
        descricao = st.text_area("Descreva o que você viu", key=f"reg_desc_{rid}", height=110,
                                 placeholder="Ex.: motociclista caiu na faixa, está consciente e sentado na calçada.",
                                 on_change=_guardar, args=(f"reg_desc_{rid}",))
        html("<b>Acionar</b> <span class='bw-nota'>(simulado: nenhum chamado real é feito)</span>")
        acion = [a for a, nome in rg.ACIONAMENTOS.items()
                 if st.checkbox(nome, key=f"reg_ac_{a}_{rid}", on_change=_guardar, args=(f"reg_ac_{a}_{rid}",))]
        html("<b>Quadros do vídeo</b>")
        video = c.clipe.video if c.clipe is not None else None
        if video is None or not Path(video).exists():
            st.caption("Sem vídeo para capturar.")
        else:
            dur = rg.duracao_s(Path(video))
            seg = st.slider("Momento do vídeo (s)", 0.0, max(dur - 0.1, 0.1), 0.0, 0.1, key=f"reg_seg_{rid}",
                            on_change=_guardar, args=(f"reg_seg_{rid}",))
            img = rg.quadro_do_video(Path(video), seg)
            if img is not None:
                st.image(img[:, :, ::-1], caption=f"Prévia do momento {seg:.1f} s".replace(".", ","), width=360)
            if st.button("Capturar este quadro", key=f"reg_cap_{rid}"):
                try:
                    q = rg.capturar(con, rid, usuario=u, video=Path(video), segundo=seg)
                    st.toast(f"Quadro anexado às {_hora(q.capturado_em)[-8:]}")
                except (ValueError, SemPermissao) as erro:
                    st.error(str(erro))
        anexos = rg.quadros(con, rid)
        if anexos:
            cols = st.columns(3)
            for i, q in enumerate(anexos):
                with cols[i % 3]:
                    if q.arquivo.exists():
                        st.image(str(q.arquivo), width="stretch", caption=(
                            f"{q.segundo:.1f} s do vídeo · capturado às {_hora(q.capturado_em)[-8:]}").replace(".", ",", 1))
                    if st.button("Remover", key=f"reg_rm_{q.id}"):
                        rg.remover_quadro(con, q.id)
                        st.rerun()
        st.write("")
        if st.button("Enviar relatório", type="primary", key=f"reg_enviar_{rid}",
                     width="stretch"):
            try:
                n = rg.enviar(con, rid, usuario=u, situacao=situacao or "", descricao=descricao, acionamentos=acion)
                st.session_state.pop(chave, None)
                st.session_state["aviso_registro"] = (
                    f"Relatório Nº {rid} enviado." + (f" A Saúde recebeu a ocorrência Nº {n} em Atendimentos." if n else ""))
                st.rerun()
            except (ValueError, SemPermissao) as erro:
                st.error(str(erro).capitalize())


def _relatorios_enviados() -> None:
    con = conexao()
    rg.migrar(con)
    lista = rg.enviados(con)
    with cartao("relatorios_enviados", "dados", "Relatórios enviados"):
        if not lista:
            st.caption("Nenhum relatório enviado ainda. Abra uma câmera para registrar.")
            return
        for r in lista:
            acion = [rg.ACIONAMENTOS[a] for a in (r["acionamentos"] or "").split(",") if a in rg.ACIONAMENTOS]
            saude = f" · ocorrência Nº {r['ocorrencia_id']} na Saúde" if r["ocorrencia_id"] else ""
            with st.expander(f"Nº {r['id']} · {r['camera']} · {r['local']} · {rg.SITUACOES.get(r['situacao'], '')} · "
                             f"{_hora(r['enviado_em'])[:-3]}"):
                html(f'<div class="bw-tempo">'
                     f'<div><span class="h">Registro</span><span>{es.esc(_nome_de(r["registrado_por"]))}, '
                     f'{_hora(r["registrado_em"])}</span></div>'
                     f'<div><span class="h">Envio</span><span>{es.esc(_nome_de(r["enviado_por"]))}, '
                     f'{_hora(r["enviado_em"])}</span></div>'
                     f'<div><span class="h">Acionou</span><span>{es.esc(", ".join(acion) or "ninguém")}{saude}'
                     f'</span></div></div>')
                html(f'<p style="margin:12px 0">{es.esc(r["descricao"])}</p>')
                anexos = [q for q in rg.quadros(con, r["id"]) if q.arquivo.exists()]
                if anexos:
                    cols = st.columns(4)
                    for i, q in enumerate(anexos):
                        cols[i % 4].image(str(q.arquivo), width="stretch", caption=(
                            f"{q.segundo:.1f} s do vídeo · capturado às {_hora(q.capturado_em)} por "
                            f"{q.capturado_por}").replace(".", ",", 1))


# ---------------------------------------------------------------- Trânsito e Saúde
def _cartao_oc(o: dict) -> None:
    origem = "aberta pela câmera" if o["origem"] == "visao" else "reportada por operador(a)"
    clipe = (f" · no clipe {o['video_id'].removeprefix('veo3_')}, aos {o['segundo']:.1f} s"
             if o.get("video_id") and o.get("segundo") is not None else "")
    local = "Largo da Concórdia"
    if o["tipo"] == "registro_camera":
        con = conexao()
        rg.migrar(con)
        r = rg.do_ocorrencia(con, o["id"])
        if r:
            local, origem, clipe = r["local"], f"registrada na {r['camera']} pelo relatório Nº {r['id']}", ""
    classe = "padrao" if o["estado"] in ("pendente", "confirmada") else "atencao"
    html(f'<div class="bw-leitura {classe}" style="padding:16px 18px;margin-bottom:10px">'
         f'<div class="titulo" style="font-size:17px">Nº {o["id"]} · {es.esc(oc.TIPOS.get(o["tipo"], o["tipo"]))}</div>'
         f'<div class="bw-nota">{es.esc(local)} · {es.esc(origem)}{es.esc(clipe)} · '
         f'{datetime.fromisoformat(o["aberta_em"]):%H:%M} · {es.esc(NOMES_ESTADO.get(o["estado"], o["estado"]))}</div></div>')


def _executar(acao: str, oc_id: int, motivo: str | None = None) -> None:
    try:
        novo = oc.aplicar(conexao(), oc_id, acao, st.session_state["usuario"], motivo=motivo)
        st.toast(f"Ocorrência Nº {oc_id}: {NOMES_ESTADO.get(novo, novo)}")
        st.rerun()
    except (SemPermissao, oc.TransicaoInvalida, ValueError) as erro:
        st.error(str(erro))


def pagina_camera() -> None:
    u = st.session_state["usuario"]
    no = no_ao_vivo()
    modo = (no.estado or {}).get("modo")
    cs = clipes()
    st.title("Validar ocorrências")
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        if not cs:
            st.info("Nenhum vídeo processado ainda. Rode `python src/visao/processar_clipes.py`.")
        else:
            idx = st.session_state.setdefault("indice_clipe", 0)
            nomes = [c.nome for c in cs]
            escolha = st.selectbox("Vídeo", ["Segue o modo do semáforo"] + nomes, key="clipe_manual")
            clipe = cs[nomes.index(escolha)] if escolha in nomes else cam.clipe_para_modo(modo, cs, idx)
            components.html(cam.html_player(clipe, modo, video_url=cam.url_estatica(clipe)), height=560)
            if st.button("Próximo vídeo"):
                st.session_state["indice_clipe"] = idx + 1
                st.rerun()
            for e in clipe.eventos:
                if e["tipo"] == "suspeita_acidente":
                    oc.abrir(conexao(), origem="visao", tipo="suspeita_acidente", video_id=f"veo3_{clipe.nome}",
                             segundo=float(e["segundo"]))
    with c2:
        with cartao("para_validar", "escudo", "Para validar"):
            pend = oc.listar(conexao(), ["pendente"])
            if not pend:
                st.caption("Nenhuma suspeita esperando validação.")
            for o in pend:
                _cartao_oc(o)
                a, b = st.columns(2)
                if a.button("Confirmar", key=f"conf{o['id']}", type="primary", width="stretch"):
                    _executar("confirmar", o["id"])
                with b.popover("Descartar", width="stretch"):
                    motivo = st.text_input("Por que é falso alarme?", key=f"mot{o['id']}")
                    if st.button("Descartar ocorrência", key=f"desc{o['id']}"):
                        _executar("descartar", o["id"], motivo)
            st.divider()
            if st.button("Reportar ocorrência", width="stretch"):
                try:
                    exigir(u.perfil, "reportar")
                    i = oc.abrir(conexao(), origem="operador", tipo="ocorrencia_reportada", usuario=u)
                    st.toast(f"Ocorrência Nº {i} aberta")
                    st.rerun()
                except SemPermissao as erro:
                    st.error(str(erro))


def pagina_confirmadas() -> None:
    st.title("Atendimentos")
    st.caption("Suspeitas que a equipe de Trânsito confirmou. Despache o atendimento e encerre quando terminar.")
    lista = oc.listar(conexao(), ["confirmada", "despachada"])
    if not lista:
        st.info("Nenhuma ocorrência confirmada agora. Quando o Trânsito confirmar uma, ela aparece aqui.")
    for o in lista:
        _cartao_oc(o)
        if o["estado"] == "confirmada":
            if st.button("Despachar ambulância (SIMULADA)", key=f"desp{o['id']}", type="primary"):
                _executar("despachar", o["id"])
        elif st.button("Encerrar atendimento", key=f"enc{o['id']}"):
            _executar("encerrar", o["id"])
    st.caption("Ao despachar, o semáforo da faixa recebe a aproximação da ambulância e abre prioridade para ela. "
               "A ambulância é simulada.")


# ---------------------------------------------------------------- equipe (gestão)
def _avatar(pf, tamanho: int = 56) -> str:
    import base64
    if pf.foto:
        src = "data:image/jpeg;base64," + base64.b64encode(pf.foto).decode()
        return (f'<img src="{src}" alt="" width="{tamanho}" height="{tamanho}" '
                f'style="border-radius:50%;object-fit:cover;flex:none">')
    return (f'<span style="width:{tamanho}px;height:{tamanho}px;border-radius:50%;background:{es.VERDE_ESC};'
            f'color:{es.CLARO};display:grid;place-items:center;font-weight:700;font-size:{tamanho // 2.4:.0f}px;'
            f'flex:none">{es.esc(pf.primeiro_nome[:1].upper())}</span>')


def _linha_pessoa(pf, extra: str = "") -> str:
    credencial = " · ".join(x for x in (pf.cargo, pf.orgao, PERFIS.get(pf.area)) if x)
    return (f'<div class="bw-card" style="display:flex;gap:14px;align-items:center;margin-bottom:10px">{_avatar(pf)}'
            f'<div style="flex:1;min-width:0"><div style="font-weight:600;font-size:16px">{es.esc(pf.nome)}</div>'
            f'<div class="bw-nota">{es.esc(credencial)}</div></div>{extra}</div>')


def pagina_perfil() -> None:
    u = st.session_state["usuario"]
    con = conexao()
    pf = au.perfil(con, u.usuario)
    st.title("Meu perfil")
    detalhes = " · ".join(x for x in (pf.email, f"matrícula {pf.matricula}" if pf.matricula else None) if x)
    html(_linha_pessoa(pf, f'<span class="bw-nota">{es.esc(detalhes)}</span>'))
    st.caption("Área, cargo, órgão e matrícula são definidos pela Gestão. Os outros dados você mesmo atualiza.")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        with cartao("seus_dados", "perfil", "Seus dados"):
            with st.form("meus_dados"):
                nome = st.text_input("Nome completo", pf.nome)
                trat = st.text_input("Como quer ser chamado(a) na plataforma", pf.nome_tratamento or "")
                tel = st.text_input("Telefone de contato (opcional)", pf.telefone or "")
                turno = st.selectbox("Turno", ["", "Manhã", "Tarde", "Noite", "Plantão 12 × 36"], placeholder="Escolha o turno",
                                     index=(["", "Manhã", "Tarde", "Noite", "Plantão 12 × 36"].index(pf.turno)
                                            if pf.turno in ("Manhã", "Tarde", "Noite", "Plantão 12 × 36") else 0))
                salvar = st.form_submit_button("Salvar dados", type="primary")
            if salvar:
                try:
                    au.atualizar_perfil(con, u.usuario, por=u.usuario, nome=nome, nome_tratamento=trat, telefone=tel,
                                        turno=turno)
                    st.session_state["usuario"] = au.Usuario(u.usuario, nome.strip() or u.nome, u.perfil)
                    st.toast("Dados salvos")
                    st.rerun()
                except (PermissionError, ValueError) as erro:
                    st.error(str(erro).capitalize() + ".")
        with cartao("foto", "camera", "Foto"):
            foto = st.file_uploader("Escolha uma foto (JPG ou PNG, até 5 MB)", type=["jpg", "jpeg", "png"])
            if foto is not None and st.button("Usar esta foto", type="primary"):
                try:
                    au.salvar_foto(con, u.usuario, foto.getvalue(), por=u.usuario)
                    st.toast("Foto atualizada")
                    st.rerun()
                except (PermissionError, ValueError) as erro:
                    st.error(str(erro).capitalize() + ".")
            st.caption("A foto é cortada em quadrado e reduzida. Ela aparece só para a sua equipe, dentro da plataforma.")
    with c2:
        with cartao("seguranca", "cadeado", "Segurança"):
            html(f'<p class="bw-nota">Entrada com senha e código do aplicativo: '
                 f'<b>{"ligada" if pf.tem_codigo else "só senha (peça um novo convite à Gestão)"}</b>.</p>')
            with st.form("senha", clear_on_submit=True):
                atual = st.text_input("Senha atual", type="password")
                nova = st.text_input("Senha nova (mínimo de 8 caracteres)", type="password")
                nova2 = st.text_input("Repita a senha nova", type="password")
                trocar = st.form_submit_button("Trocar senha")
            if trocar:
                if nova != nova2:
                    st.error("As senhas novas não conferem.")
                else:
                    try:
                        au.trocar_senha(con, u.usuario, atual, nova)
                        st.success("Senha trocada.")
                    except ValueError as erro:
                        st.error(str(erro).capitalize() + ".")
        with cartao("seus_ultimos_acessos", "relogio", "Seus últimos acessos"):
            nomes = {"entrada": "Entrou", "saida": "Saiu", "falha": "Senha errada", "codigo_errado": "Código errado",
                     "bloqueio": "Bloqueado por tentativas", "expirou": "Sessão expirou", "convite": "Convite criado",
                     "convite_aceito": "Ativou o acesso"}
            itens = "".join(f'<div><span class="h">{datetime.fromisoformat(a["timestamp"]):%d/%m %H:%M}</span>'
                            f'<span>{es.esc(nomes.get(a["evento"], a["evento"]))}</span></div>'
                            for a in au.meus_acessos(con, u.usuario))
            html(f'<div class="bw-tempo">{itens}</div>')
            st.caption("Se aparecer um acesso que você não fez, troque a senha e avise a Gestão.")


def pagina_equipe() -> None:
    u = st.session_state["usuario"]
    st.title("Equipe")
    st.caption("Convide quem vai usar a plataforma. A pessoa recebe um link, cria a própria senha e liga o código do "
               "aplicativo autenticador. Ninguém entra só com a senha.")
    con = conexao()
    with st.expander("Convidar uma pessoa", expanded=False):
        with st.form("convidar", clear_on_submit=True):
            a, b = st.columns(2)
            nome = a.text_input("Nome completo", key="conv_nome")
            email = b.text_input("E-mail institucional", key="conv_email")
            c, d = st.columns(2)
            area = c.selectbox("Área", list(PERFIS), format_func=PERFIS.get)
            cargo = d.text_input("Cargo ou função", key="conv_cargo")
            e, f = st.columns(2)
            orgao = e.text_input("Órgão ou equipe", key="conv_orgao")
            matricula = f.text_input("Matrícula (opcional)", key="conv_matricula")
            enviar = st.form_submit_button("Gerar convite", type="primary")
    if enviar:
        try:
            exigir(u.perfil, "convidar")
            token = au.convidar_pessoa(con, email=email, area=area, nome=nome, cargo=cargo, orgao=orgao,
                                       matricula=matricula)
            st.session_state["ultimo_convite"] = (email, f"http://localhost:8611/?convite={token}")
        except (SemPermissao, ValueError) as erro:
            st.error(str(erro).capitalize() + ".")
    if st.session_state.get("ultimo_convite"):
        email, link = st.session_state["ultimo_convite"]
        st.success(f"Convite criado para {email}. Ele vale por {au.CONVITE_H} horas e só pode ser usado uma vez.")
        st.code(link, language=None)
        st.caption("Nesta versão, copie o link e envie à pessoa. Na versão final, ele sai por e-mail automaticamente.")
    with cartao("quem_tem_acesso", "perfil", "Quem tem acesso"):
        for pf in au.equipe(con):
            if not pf.ativo:
                sit, cor = "Desativado", es.MUTED
            elif pf.convite_pendente:
                sit, cor = "Convite enviado", es.AMBAR
            elif pf.tem_codigo:
                sit, cor = "Ativo, com código do aplicativo", es.VERDE
            else:
                sit, cor = "Ativo só com senha (conta antiga)", es.AMBAR
            html(_linha_pessoa(pf, f'<span style="color:{cor};font-size:14px;font-weight:600">{sit}</span>'))
            if pf.ativo and pf.usuario != u.usuario:
                with st.popover(f"Gerenciar {pf.primeiro_nome}"):
                    with st.form(f"g_{pf.usuario}"):
                        nova_area = st.selectbox("Área", list(PERFIS), index=list(PERFIS).index(pf.area),
                                                 format_func=PERFIS.get, key=f"ga_{pf.usuario}")
                        novo_cargo = st.text_input("Cargo ou função", pf.cargo or "", key=f"gc_{pf.usuario}")
                        ok = st.form_submit_button("Salvar")
                    if ok:
                        au.atualizar_perfil(con, pf.usuario, por=u.usuario, area=nova_area, cargo=novo_cargo)
                        st.rerun()
                    if st.button("Desativar acesso", key=f"gd_{pf.usuario}"):
                        au.desativar(con, pf.usuario, por=u.usuario)
                        st.rerun()


# ---------------------------------------------------------------- navegação
PAGINAS = {
    "visao": st.Page(pagina_visao_geral, title="Visão geral", url_path="visao-geral",
                     default=True),
    "painel": st.Page(pagina_painel, title="Painel", url_path="painel"),
    "cameras": st.Page(pagina_cameras, title="Câmeras", url_path="cameras"),
    "ocorrencias": st.Page(pagina_ocorrencias_gestao, title="Ocorrências",
                           url_path="ocorrencias"),
    "sala": st.Page(pagina_sala, title="Sala de controle", url_path="sala-de-controle"),
    "camera": st.Page(pagina_camera, title="Validar ocorrências", url_path="validar"),
    "confirmadas": st.Page(pagina_confirmadas, title="Atendimentos",
                           url_path="atendimentos"),
    "demos": st.Page(pagina_demonstracoes, title="Demonstrações", url_path="demonstracoes"),
    "sobre": st.Page(pagina_sobre, title="Sobre", url_path="sobre"),
    "equipe": st.Page(pagina_equipe, title="Equipe", url_path="equipe"),
    "sair": st.Page(sair, title="Sair", url_path="sair"),
}
POR_PERFIL = {"gestao": ["visao", "painel", "cameras", "ocorrencias", "sala", "equipe", "demos", "perfil", "sobre", "sair"],
              "transito": ["visao", "camera", "cameras", "sala", "demos", "perfil", "sobre", "sair"],
              "saude": ["visao", "confirmadas", "cameras", "sala", "demos", "perfil", "sobre", "sair"]}


def _login_em(chave: str):
    """A tela de entrada publicada também no endereço de uma página interna (cada uma com nome próprio)."""
    def entrada() -> None:
        tela_login()
    entrada.__name__ = f"entrar_{chave}"
    return entrada


def main() -> None:
    st.set_page_config(page_title="BetterWay", page_icon=str(MARCA / "betterway-simbolo.png"), layout="wide")
    html(es.tokens(tema()) + es.CSS + cp.CSS)
    u = usuario()
    if u is None:
        # sem login, qualquer endereço do app (ex.: recarregar na Sala de controle) abre a entrada, sem "Page not found"
        entradas = [st.Page(tela_login, title="Entrar", url_path="entrar", default=True)]
        for chave, pagina in PAGINAS.items():
            if pagina.url_path and pagina.url_path != "entrar":      # a página padrão já cai na entrada
                entradas.append(st.Page(_login_em(chave), title="Entrar", url_path=pagina.url_path))
        entradas.append(st.Page(_login_em("perfil"), title="Entrar", url_path="perfil"))
        st.navigation(entradas, position="hidden").run()
        return
    fundo_claro = tema() == "light"
    st.logo(str(MARCA / f"betterway-logo-horizontal-{'fundo-claro' if fundo_claro else 'escuro'}.png"), size="large")
    pf = au.perfil(conexao(), u.usuario)
    PAGINAS["perfil"] = st.Page(pagina_perfil, title=pf.primeiro_nome if pf else "Meu perfil", url_path="perfil")
    nav = st.navigation([PAGINAS[k] for k in POR_PERFIL[u.perfil]], position="top")
    alvo = st.session_state.pop("ir_para", None)          # atalho interno (e para os testes)
    if alvo in POR_PERFIL[u.perfil]:
        st.switch_page(PAGINAS[alvo])
    with st.container(key="leitor"):                      # acessibilidade: lê a página em voz alta
        components.html(leitor.html_botao(), height=40)
    claro = tema() == "light"
    html(f"<style>.st-key-tema_btn button{{background-image:"
         f"{es.icone_url('lua' if claro else 'sol', '#1A1D21' if claro else '#F5F5F2')} !important}}</style>")
    with st.container(key="tema_btn"):
        st.button("Mudar o tema", key="tema_trocar",
                  help="Mudar para o modo escuro" if claro else "Mudar para o modo claro", on_click=_trocar_tema)
    nav.run()


main()
