"""Plataforma BetterWay: visão geral, painel de risco, ocorrências, sala de controle e estudos, por perfil.

    streamlit run src/operador/app.py          (de 1TIAO/GLOBAL-SOLUTION-2)

Antes, crie os usuários (senhas fora do Git):
    python src/operador/autenticacao.py criar gestao1 gestao "Gestão 1"

Specs: docs/specs/2026-11-17-interface-operador-design.md. Marca: kit BetterWay v2 (tema escuro, Montserrat).
O banco pode ser trocado por VIA_SEGURA_DB; BETTERWAY_SEM_MQTT=1 roda sem broker e BETTERWAY_SEM_CLIPES=1 sem
vídeos (testes).
"""
from __future__ import annotations

import os
import sqlite3
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
import camera as cam  # noqa: E402
import estilo as es  # noqa: E402
import leitura as lt  # noqa: E402
import mensagens as m  # noqa: E402
import ocorrencias as oc  # noqa: E402
import padrao as pdr  # noqa: E402
from no_ao_vivo import CENARIOS, NoAoVivo, comando_cenario  # noqa: E402
from perfis import PERFIS, SemPermissao, exigir, pode  # noqa: E402

DB = Path(os.environ.get("VIA_SEGURA_DB", RAIZ / "data" / "processed" / "seguranca_viaria.db"))
EVID = RAIZ / "docs" / "evidencias"
MARCA = RAIZ / "assets" / "marca"
PILOTO, LAT, LON = 139, -23.54183, -46.61613          # Largo da Concórdia (Brás)
VIDEO_DEMO = "cdmx_pexels_25775484"
ROTULOS_CENARIO = {"normal": "Normal", "pedestre": "Pedestre", "escola": "Escola", "chuva": "Chuva",
                   "alagamento": "Alagamento", "ambulancia": "Ambulância"}
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


def tela_login() -> None:
    _, meio, _ = st.columns([1, 1.15, 1])
    with meio:
        html('<div class="bw-login-espaco"></div>')
        logo = MARCA / "betterway-logo-horizontal-escuro.png"
        if logo.exists():
            st.image(str(logo), width="stretch")
        if st.session_state.get("aviso_login"):
            st.info(st.session_state["aviso_login"])
        with st.form("login"):
            nome = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar", type="primary", width="stretch")
        if entrar:
            r = au.autenticar(conexao(), nome, senha)
            if r.ok:
                st.session_state.clear()
                st.session_state["usuario"] = r.usuario
                st.session_state["ultimo_uso"] = datetime.now().replace(microsecond=0)
                st.rerun()
            else:
                st.error(r.mensagem)


def sair() -> None:
    u = st.session_state.get("usuario")
    if u is not None:
        au.registrar_acesso(conexao(), u.usuario, "saida")
    st.session_state.clear()
    st.rerun()


def html(conteudo: str) -> None:
    st.markdown(conteudo, unsafe_allow_html=True)


# ---------------------------------------------------------------- visão geral
def pagina_visao_geral() -> None:
    u = st.session_state["usuario"]
    cl = consultar("SELECT COUNT(*) AS n FROM clusters WHERE rank_urbano IS NOT NULL")
    n_grupos = int(cl.n.iloc[0]) if not cl.empty else None
    pil = consultar("SELECT COUNT(*) AS n, SUM(fatal) AS f FROM sinistros WHERE cluster_id = ?", (PILOTO,))
    n_pil, f_pil = (int(pil.n.iloc[0]), int(pil.f.iloc[0] or 0)) if not pil.empty else (None, None)
    html(f"""<div class="bw-hero"><div>
      <div class="chamada">Mais seguro para quem atravessa, <span class="fim">mais rápido para quem dirige.</span></div>
      <p>A BetterWay junta quatro anos de atropelamentos registrados em São Paulo, uma câmera que entende a faixa de
      pedestres e um semáforo conectado. Ela mostra onde e quando o risco aparece, dá mais tempo a quem precisa
      atravessar e abre caminho para a ambulância. Sem identificar ninguém.</p></div></div>""")
    html('<div class="bw-secao">O que a plataforma faz</div>')
    html(f"""<div class="bw-grid">
      <div class="bw-card"><span class="icone">{es.icone("vida")}</span><div class="verbo">to live</div>
        <h3>Encontra onde se atropela</h3><p>Agrupa os atropelamentos do Infosiga-SP (2022–2025) em pontos críticos
        e ordena a cidade por prioridade{f": {n_grupos} pontos urbanos" if n_grupos else ""}. No piloto, avisa
        quando a situação de agora repete a dos acidentes.</p></div>
      <div class="bw-card"><span class="icone">{es.icone("pedestre")}</span><div class="verbo">to be free</div>
        <h3>Dá tempo a quem precisa</h3><p>A câmera reconhece cadeira de rodas, andador, muleta e bengala, e o
        semáforo segura o verde até a pessoa terminar de atravessar.</p></div>
      <div class="bw-card"><span class="icone">{es.icone("ambulancia")}</span><div class="verbo">to move</div>
        <h3>Abre caminho para a ambulância</h3><p>Quando uma ambulância se aproxima, o semáforo dá prioridade a ela,
        sempre esperando a faixa esvaziar. No resto do tempo, o sinal reage à fila de carros.</p></div>
    </div>""")
    html('<div class="bw-secao">Como funciona, do começo ao fim</div>')
    html("""<div class="bw-passos">
      <div class="bw-passo"><span class="n">1</span><b>A câmera vê a faixa</b><span>Conta quem atravessa, mede o
        tempo e percebe conflitos com veículos. Rostos e placas saem borrados.</span></div>
      <div class="bw-passo"><span class="n">2</span><b>A central decide</b><span>Junta câmera, chuva, horário e o
        histórico do local, e escolhe o modo do semáforo.</span></div>
      <div class="bw-passo"><span class="n">3</span><b>O nó na faixa age</b><span>O ESP32 estende o verde, avisa
        os motoristas no painel de LED ou dá prioridade à ambulância.</span></div>
      <div class="bw-passo"><span class="n">4</span><b>A equipe valida</b><span>Trânsito confirma cada suspeita de
        acidente; Saúde recebe o alerta e despacha o atendimento.</span></div>
    </div>""")
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        html('<div class="bw-secao">O piloto: Largo da Concórdia, no Brás</div>')
        texto = (f"{n_pil} atropelamentos entre 2022 e 2025, {f_pil} com morte. " if n_pil else "") + \
            "É um dos pontos mais críticos da cidade no ranking urbano, numa avenida de seis faixas com " \
            "16 metros de travessia: mais do que muita gente consegue atravessar no tempo do verde."
        html(f'<p class="bw-nota" style="font-size:16px;color:#D9DAD5">{es.esc(texto)}</p>')
    with c2:
        html('<div class="bw-secao">Por onde começar</div>')
        destinos = {"gestao": [("painel", "Painel: o risco de agora e por quê"),
                               ("ocorrencias", "Ocorrências: o que aconteceu e em quanto tempo"),
                               ("estudos", "Estudos: as evidências de que funciona")],
                    "transito": [("camera", "Câmera e ocorrências para validar")],
                    "saude": [("confirmadas", "Ocorrências confirmadas para atender")]}[u.perfil]
        for url, rotulo in destinos:
            st.page_link(PAGINAS[url], label=rotulo, icon=":material/arrow_forward:")
    html('<p class="bw-nota">Privacidade: nenhum rosto é reconhecido e nenhuma imagem é guardada; o sistema guarda só '
         'números e horários.</p>')


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
    hist = consultar("SELECT data_sinistro, hora, chuva_mm FROM sinistros WHERE cluster_id = ?", (PILOTO,))
    padrao = pdr.padrao_agora(hist, quando, chuva)
    rk = risco_em(quando.replace(second=0, microsecond=0).isoformat(), chuva or 0.0)
    media = risco_medio_do_ponto(quando.weekday() < 5)
    vezes_local = rk["risco_relativo"] / media if rk and media else None
    leit = lt.ler(padrao, camera_agora(agora), chuva, vezes_local, rk["risco_relativo"] if rk else None)
    lt.registrar(conexao(), leit, quando, simulado=sim)
    html(_cartao_leitura(leit, quando, sim))

    no = no_ao_vivo()
    abertas = oc.listar(conexao(), ["pendente", "confirmada", "despachada"])
    tempos = _tempos_ocorrencias()
    conf = tempos["Até confirmar (s)"].dropna() if not tempos.empty else pd.Series(dtype=float)
    k = st.columns(4)
    with k[0]:
        html(es.kpi("Modo do semáforo", cam.NOMES_MODO.get((no.estado or {}).get("modo"), "Sem sinal do nó"),
                    "nó ESP32 na faixa"))
    with k[1]:
        html(es.kpi("Risco agora", f"{rk['risco_relativo']:.1f}×".replace(".", ",") if rk else "—",
                    "a média da cidade"))
    with k[2]:
        html(es.kpi("Ocorrências em aberto", str(len(abertas)), "aguardando validação ou atendimento"))
    with k[3]:
        html(es.kpi("Tempo até confirmar", f"{conf.mean():.0f} s" if len(conf) else "—", "média das ocorrências"))
    st.write("")
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        st.subheader("Mapa de risco da cidade")
        _mapa()
    with c2:
        st.subheader("Linha do tempo das leituras")
        hist_l = lt.historico(conexao(), 12)
        if not hist_l:
            st.caption("A primeira leitura aparece aqui.")
        linhas = "".join(
            f'<div><span class="h">{datetime.fromisoformat(r["timestamp"]):%H:%M}</span><span>'
            f'{es.selo_nivel(r["nivel"])}{" <span class=bw-nota>simulada</span>" if r["simulado"] else ""}'
            f'<br><span class="bw-nota">{es.esc(r["resumo"])}</span></span></div>' for r in hist_l)
        html(f'<div class="bw-tempo">{linhas}</div>')


def _mapa() -> None:
    import pydeck as pdk
    cl = consultar("SELECT * FROM clusters WHERE rank_urbano IS NOT NULL")
    if cl.empty:
        st.info("Sem pontos críticos no banco. Gere-os com os notebooks 03 e 04.")
        return
    cl = cl.assign(raio=(cl["peso"].clip(lower=1) ** 0.5) * 80, via=cl["via_principal"].fillna("—"))
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
    html('<p class="bw-nota">Cada ponto é um grupo de atropelamentos (Infosiga-SP, 2022–2025). Vermelho: entre os 20 '
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


def pagina_ocorrencias_gestao() -> None:
    st.title("Ocorrências")
    st.caption("Cada suspeita de acidente passa pelo Trânsito, que confirma ou descarta, e pela Saúde, que despacha o "
               "atendimento. Aqui está quanto tempo cada etapa levou.")
    df = _tempos_ocorrencias()
    if df.empty:
        st.info("Nenhuma ocorrência registrada ainda. Quando a câmera ou um operador abrir uma, ela aparece aqui.")
        return
    k = st.columns(4)
    with k[0]:
        html(es.kpi("Ocorrências", str(len(df)), "no total"))
    with k[1]:
        html(es.kpi("Confirmadas", str(int(df["Até confirmar (s)"].notna().sum())), "pelo Trânsito"))
    with k[2]:
        html(es.kpi("Descartadas", str(int(df["Motivo do descarte"].notna().sum())), "falso alarme"))
    with k[3]:
        d = df["Até despachar (s)"].dropna()
        html(es.kpi("Até despachar", f"{d.mean():.0f} s" if len(d) else "—", "média, depois de confirmada"))
    st.write("")
    vis = df.copy()
    for c in ("Até confirmar (s)", "Até despachar (s)", "Atendimento (s)"):
        vis[c] = vis[c].map(lambda v: "—" if pd.isna(v) else f"{v:.0f}")
    vis["Motivo do descarte"] = vis["Motivo do descarte"].fillna("—")
    st.dataframe(vis, hide_index=True, width="stretch")


# ---------------------------------------------------------------- estudos
def pagina_estudos() -> None:
    st.title("Estudos")
    st.caption("As evidências de que a plataforma funciona: simulação do trânsito e testes da câmera.")
    aba = st.segmented_control("Estudo", ["Simulação do cruzamento", "Clipes sintéticos da câmera"],
                               default="Simulação do cruzamento", key="sub_estudos",
                               label_visibility="collapsed") or "Simulação do cruzamento"
    if aba == "Simulação do cruzamento":
        _estudo_a()
    else:
        _clipes_sinteticos()


def _barras(rotulo: str, sem: float, com: float, unidade: str, menor_melhor: bool = True) -> str:
    topo = max(sem, com) or 1
    melhor = (com < sem) if menor_melhor else (com > sem)
    var = (com - sem) / sem * 100 if sem else 0
    cor_var = es.VERDE if melhor else es.ALERTA_INK
    fmt = lambda v: f"{v:.1f}".replace(".", ",")  # noqa: E731
    return (f'<div class="bw-card"><div class="r" style="color:{es.MUTED};font-size:13px;font-weight:500">'
            f'{es.esc(rotulo)}</div>'
            f'<div style="display:grid;grid-template-columns:70px 1fr 64px;gap:8px;align-items:center;margin-top:12px">'
            f'<span class="bw-nota">Hoje</span><div style="height:12px;border-radius:6px;background:#4A5058;'
            f'width:{sem / topo * 100:.0f}%"></div><b style="text-align:right">{fmt(sem)} {unidade}</b>'
            f'<span class="bw-nota">BetterWay</span><div style="height:12px;border-radius:6px;background:{es.VERDE};'
            f'width:{com / topo * 100:.0f}%"></div><b style="text-align:right">{fmt(com)} {unidade}</b></div>'
            f'<div style="margin-top:10px;font-weight:700;color:{cor_var}">{"−" if var < 0 else "+"}'
            f'{abs(var):.0f}%</div></div>')


def _estudo_a() -> None:
    import cruzamento as cz
    st.subheader("O mesmo cruzamento, hoje e com a BetterWay")
    st.markdown("Escolha uma situação e compare os dois lados: as mesmas pessoas e os mesmos carros, muda só o "
                "semáforo. É a simulação no SUMO de um cruzamento com as medidas do Largo da Concórdia.")
    cena = st.segmented_control("Situação", list(cz.CENAS), format_func=cz.CENAS.get, default="pedestre",
                                key="cena_estudo", label_visibility="collapsed") or "pedestre"
    try:
        dados, met = cz.carregar(cena)
    except FileNotFoundError:
        st.info("Cena ainda não exportada: rode `python src/simulacao/animacao_estudo_a.py --json`.")
        return
    components.html(cz.html_cruzamento(dados, met), height=760, scrolling=False)
    p = EVID / "estudo_a" / "estudo_a_resumo.csv"
    if not p.exists():
        return
    r = pd.read_csv(p, sep=";", encoding="utf-8-sig").set_index(["comparacao", "sistema"])
    st.subheader("Semáforo que reage à fila de carros")
    st.caption("Média de 5 rodadas de 10 minutos simulados. Resultado esperado de simulação, não medição na rua.")
    s, c = r.loc[("semaforo", "sem")], r.loc[("semaforo", "com")]
    html('<div class="bw-grid">' +
         _barras("Atraso médio de cada carro", s.atraso_medio_carro_s, c.atraso_medio_carro_s, "s") +
         _barras("CO₂ por carro", s.co2_medio_g_por_carro, c.co2_medio_g_por_carro, "g") +
         _barras("Espera média de quem atravessa", s.espera_media_pedestre_s, c.espera_media_pedestre_s, "s") +
         '</div>')
    html(f'<p class="bw-nota">O custo dessa troca: com o sinal reagindo só à fila de carros, mais pedestres comuns '
         f'ficam na faixa quando o sinal deles fecha ({s.surpreendidos_comum:.0f} → {c.surpreendidos_comum:.0f} por '
         f'rodada). Por isso a BetterWay combina esse modo com a extensão do verde para quem ainda está atravessando.'
         f'</p>')


def _clipes_sinteticos() -> None:
    st.subheader("A câmera testada em situações difíceis de filmar")
    st.caption("Clipes curtos gerados por IA (Veo 3), cada um com o resultado esperado. Mostram a regra funcionando; "
               "não medem desempenho na rua, por isso ficam separados dos resultados com vídeo real.")
    p = EVID / "operador" / "avaliacao_clipes.csv"
    if not p.exists():
        st.info("Os clipes ainda estão sendo gerados. Quando forem processados, o resultado de cada um aparece aqui.")
        return
    df = pd.read_csv(p, sep=";", encoding="utf-8-sig")
    html(es.kpi("Clipes com o resultado esperado", f"{int(df.acerto.sum())} de {len(df)}", "avaliação sintética"))
    st.dataframe(df, hide_index=True, width="stretch")


# ---------------------------------------------------------------- sala de controle
def pagina_sala() -> None:
    u = st.session_state["usuario"]
    st.title("Sala de controle")
    st.caption("O nó da faixa do Largo da Concórdia ao vivo: o que o semáforo está fazendo agora e o que ele relatou.")
    no = no_ao_vivo()

    @st.fragment(run_every=3)
    def estado():
        e = no.estado or {}
        k = st.columns(3)
        with k[0]:
            html(es.kpi("Modo do semáforo", cam.NOMES_MODO.get(e.get("modo"), "Sem sinal do nó"),
                        f"atualizado às {no.estado_recebido_em:%H:%M:%S}" if no.estado_recebido_em else
                        "o nó ainda não respondeu"))
        with k[1]:
            html(es.kpi("Fase", (e.get("fase") or "—").replace("_", " ").capitalize(), "ciclo do semáforo"))
        with k[2]:
            html(es.kpi("Conexão", "Conectada" if no.conectado else "Desconectada", "com a central (MQTT)"))
        if no.eventos:
            st.write("")
            st.dataframe(pd.DataFrame(list(no.eventos))[["recebido_em", "tipo"]].rename(
                columns={"recebido_em": "Quando", "tipo": "O que o nó relatou"}), hide_index=True,
                width="stretch")
    estado()
    st.write("")
    if pode(u.perfil, "cenario"):
        st.subheader("Mudar o modo do semáforo")
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


# ---------------------------------------------------------------- Trânsito e Saúde
def _cartao_oc(o: dict) -> None:
    origem = "aberta pela câmera" if o["origem"] == "visao" else "reportada por operador(a)"
    clipe = f" · no clipe {o['video_id'].removeprefix('veo3_')}, aos {o['segundo']:.1f} s" if o.get("video_id") else ""
    classe = "padrao" if o["estado"] in ("pendente", "confirmada") else "atencao"
    html(f'<div class="bw-leitura {classe}" style="padding:16px 18px;margin-bottom:10px">'
         f'<div class="titulo" style="font-size:17px">Nº {o["id"]} · {es.esc(oc.TIPOS.get(o["tipo"], o["tipo"]))}</div>'
         f'<div class="bw-nota">Largo da Concórdia · {origem}{es.esc(clipe)} · '
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
    st.title("Câmera e ocorrências")
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        if not cs:
            st.info("Nenhum vídeo processado ainda. Rode `python src/visao/processar_clipes.py`.")
        else:
            idx = st.session_state.setdefault("indice_clipe", 0)
            nomes = [c.nome for c in cs]
            escolha = st.selectbox("Vídeo", ["Segue o modo do semáforo"] + nomes, key="clipe_manual")
            clipe = cs[nomes.index(escolha)] if escolha in nomes else cam.clipe_para_modo(modo, cs, idx)
            components.html(cam.html_player(clipe, modo), height=560)
            if st.button("Próximo vídeo"):
                st.session_state["indice_clipe"] = idx + 1
                st.rerun()
            for e in clipe.eventos:
                if e["tipo"] == "suspeita_acidente":
                    oc.abrir(conexao(), origem="visao", tipo="suspeita_acidente", video_id=f"veo3_{clipe.nome}",
                             segundo=float(e["segundo"]))
    with c2:
        st.subheader("Para validar")
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
    st.title("Ocorrências confirmadas")
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


# ---------------------------------------------------------------- navegação
PAGINAS = {
    "visao": st.Page(pagina_visao_geral, title="Visão geral", icon=":material/home:", url_path="visao-geral",
                     default=True),
    "painel": st.Page(pagina_painel, title="Painel", icon=":material/monitoring:", url_path="painel"),
    "ocorrencias": st.Page(pagina_ocorrencias_gestao, title="Ocorrências", icon=":material/assignment:",
                           url_path="ocorrencias"),
    "sala": st.Page(pagina_sala, title="Sala de controle", icon=":material/traffic:", url_path="sala-de-controle"),
    "estudos": st.Page(pagina_estudos, title="Estudos", icon=":material/science:", url_path="estudos"),
    "camera": st.Page(pagina_camera, title="Câmera e ocorrências", icon=":material/videocam:", url_path="camera"),
    "confirmadas": st.Page(pagina_confirmadas, title="Ocorrências confirmadas", icon=":material/emergency:",
                           url_path="confirmadas"),
    "sair": st.Page(sair, title="Sair", icon=":material/logout:", url_path="sair"),
}
POR_PERFIL = {"gestao": ["visao", "painel", "ocorrencias", "sala", "estudos", "sair"],
              "transito": ["visao", "camera", "sala", "sair"],
              "saude": ["visao", "confirmadas", "sala", "sair"]}


def main() -> None:
    st.set_page_config(page_title="BetterWay", page_icon=str(MARCA / "betterway-simbolo.png"), layout="wide")
    html(es.CSS)
    u = usuario()
    if u is None:
        st.navigation([st.Page(tela_login, title="Entrar", url_path="entrar", default=True)], position="hidden").run()
        return
    st.logo(str(MARCA / "betterway-logo-horizontal-escuro.png"), size="large")
    nav = st.navigation([PAGINAS[k] for k in POR_PERFIL[u.perfil]], position="top")
    alvo = st.session_state.pop("ir_para", None)          # atalho interno (e para os testes)
    if alvo in POR_PERFIL[u.perfil]:
        st.switch_page(PAGINAS[alvo])
    nav.run()


main()
