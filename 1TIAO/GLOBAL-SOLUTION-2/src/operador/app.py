"""Interface do operador BetterWay: Trânsito valida, Saúde despacha, Gestão acompanha; sala de controle do nó.

    streamlit run src/operador/app.py          (de 1TIAO/GLOBAL-SOLUTION-2)

Antes, crie os usuários (senhas fora do Git):
    python src/operador/autenticacao.py criar transito1 transito "Operador(a) Trânsito 1"

Spec: docs/specs/2026-11-17-interface-operador-design.md. Ambiente de demonstração: sem integração com CET ou SAMU.
O banco pode ser trocado por VIA_SEGURA_DB; BETTERWAY_SEM_MQTT=1 roda sem broker (testes).
"""
from __future__ import annotations

import importlib.util
import os
import sqlite3
import sys
from datetime import datetime
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
import mensagens as m  # noqa: E402
import ocorrencias as oc  # noqa: E402
from no_ao_vivo import CENARIOS, NoAoVivo, comando_cenario  # noqa: E402
from perfis import PERFIS, SemPermissao, exigir, pode  # noqa: E402

DB = Path(os.environ.get("VIA_SEGURA_DB", RAIZ / "data" / "processed" / "seguranca_viaria.db"))
EVID = RAIZ / "docs" / "evidencias"
LOGO = RAIZ / "assets" / "marca" / "betterway-logo-horizontal-claro.png"
AVISO = "Ambiente de demonstração · sem integração com CET ou SAMU"
LAT, LON = -23.54183, -46.61613          # Largo da Concórdia (grupo 139)
ROTULOS_CENARIO = {"normal": "Normal", "pedestre": "Pedestre", "escola": "Escola", "chuva": "Chuva",
                   "alagamento": "Alagamento", "ambulancia": "Ambulância"}
PAGINAS = {
    "transito": ["Câmera e ocorrências", "Sala de controle"],
    "saude": ["Ocorrências confirmadas", "Sala de controle"],
    "gestao": ["Painel", "Ocorrências", "Estudo A (SUMO)", "Clipes sintéticos", "Sala de controle"],
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stButton button, input { font-family: 'Montserrat', sans-serif; }
[data-testid="stSidebar"] { background: #1A1D21; }
[data-testid="stSidebar"] * { color: #F4F4EF; }
[data-testid="stSidebar"] .stButton button { background: #2a2e33; border: 1px solid #9aa1aa; }
.bw-aviso { background: #FFB000; color: #1A1D21; padding: 6px 14px; border-radius: 8px; font-weight: 600;
            font-size: 13px; margin-bottom: 8px; }
.bw-card { background: #fff; border-radius: 16px; padding: 14px 18px; border-left: 6px solid #00C27A; margin-bottom: 10px; }
.bw-card.alerta { border-left-color: #E63946; }
.bw-card.ambar { border-left-color: #FFB000; }
</style>
"""


# ---------------------------------------------------------------- recursos
def conexao() -> sqlite3.Connection:
    con = sqlite3.connect(DB, check_same_thread=False, timeout=10)
    au.migrar(con)
    oc.migrar(con)
    return con


@st.cache_resource
def no_ao_vivo() -> NoAoVivo:
    if os.environ.get("BETTERWAY_SEM_MQTT"):
        return NoAoVivo()
    return NoAoVivo.conectar(banco=str(DB))


@st.cache_data(ttl=300, show_spinner=False)
def risco_agora(hora: str) -> dict | None:
    try:
        from risco import risco
        return risco(LAT, LON, datetime.fromisoformat(hora), 0.0)
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def clipes() -> list[cam.Clipe]:
    if os.environ.get("BETTERWAY_SEM_CLIPES"):
        return []
    return cam.clipes_disponiveis()


# ---------------------------------------------------------------- sessão
def usuario_da_sessao() -> au.Usuario | None:
    u, ultimo = st.session_state.get("usuario"), st.session_state.get("ultimo_uso")
    if u is None:
        return None
    if not au.sessao_valida(ultimo):
        au.registrar_acesso(conexao(), u.usuario, "expirou")
        st.session_state.clear()
        st.session_state["aviso_login"] = "Sessão expirada por inatividade. Entre de novo."
        return None
    st.session_state["ultimo_uso"] = datetime.now().replace(microsecond=0)
    return u


def tela_login() -> None:
    _, meio, _ = st.columns([1, 1.2, 1])
    with meio:
        if LOGO.exists():
            st.image(str(LOGO), use_container_width=True)
        st.markdown("#### Central de operação da faixa")
        if st.session_state.get("aviso_login"):
            st.info(st.session_state["aviso_login"])
        with st.form("login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if entrar:
            r = au.autenticar(conexao(), usuario, senha)
            if r.ok:
                st.session_state.clear()
                st.session_state["usuario"] = r.usuario
                st.session_state["ultimo_uso"] = datetime.now().replace(microsecond=0)
                st.rerun()
            else:
                st.error(r.mensagem)
        st.caption("Acesso por perfil: Trânsito, Saúde e Gestão. Usuários criados pela equipe (CLI).")


# ---------------------------------------------------------------- partes comuns
def _ts(iso: str | None) -> str:
    return datetime.fromisoformat(iso).strftime("%d/%m %H:%M:%S") if iso else "—"


def card_ocorrencia(o: dict, classe: str = "alerta") -> None:
    origem = "visão (protótipo)" if o["origem"] == "visao" else "reportada pelo operador"
    clipe = f" · clipe {o['video_id']} aos {o['segundo']:.1f} s" if o.get("video_id") else ""
    st.markdown(f"<div class='bw-card {classe}'><b>#{o['id']} · {oc.TIPOS.get(o['tipo'], o['tipo'])}</b> — "
                f"Largo da Concórdia (grupo {o['cluster_id']})<br><small>{origem}{clipe} · aberta em "
                f"{_ts(o['aberta_em'])} · estado: <b>{o['estado']}</b></small></div>", unsafe_allow_html=True)


def executar(acao: str, usuario: au.Usuario, oc_id: int, motivo: str | None = None) -> None:
    try:
        novo = oc.aplicar(conexao(), oc_id, acao, usuario, motivo=motivo)
        st.toast(f"Ocorrência #{oc_id}: {novo}")
        st.rerun()
    except (SemPermissao, oc.TransicaoInvalida, ValueError) as erro:
        st.error(str(erro))


# ---------------------------------------------------------------- Trânsito
def pagina_transito(u: au.Usuario) -> None:
    no = no_ao_vivo()
    modo = (no.estado or {}).get("modo")
    cs = clipes()
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Câmera da faixa")
        if not cs:
            st.info("Nenhum clipe processado. Rode `python src/visao/processar_clipes.py`.")
        else:
            idx = st.session_state.setdefault("indice_clipe", 0)
            nomes = [c.nome for c in cs]
            escolha = st.selectbox("Clipe", ["(segue o modo do nó)"] + nomes, key="clipe_manual")
            clipe = cs[nomes.index(escolha)] if escolha in nomes else cam.clipe_para_modo(modo, cs, idx)
            if st.button("Próximo clipe"):
                st.session_state["indice_clipe"] = idx + 1
                st.rerun()
            components.html(cam.html_player(clipe, modo), height=560)
            # a visão "vê" a suspeita no clipe em exibição: abre a ocorrência (idempotente)
            for e in clipe.eventos:
                if e["tipo"] == "suspeita_acidente":
                    oc.abrir(conexao(), origem="visao", tipo="suspeita_acidente", video_id=f"veo3_{clipe.nome}",
                             segundo=float(e["segundo"]))
    with c2:
        st.subheader("Ocorrências pendentes")
        pend = oc.listar(conexao(), ["pendente"])
        if not pend:
            st.caption("Nenhuma pendente.")
        for o in pend:
            card_ocorrencia(o)
            a, b = st.columns(2)
            if a.button("Confirmar", key=f"conf{o['id']}", type="primary", use_container_width=True):
                executar("confirmar", u, o["id"])
            with b.popover("Descartar", use_container_width=True):
                motivo = st.text_input("Motivo", key=f"mot{o['id']}")
                if st.button("Descartar ocorrência", key=f"desc{o['id']}"):
                    executar("descartar", u, o["id"], motivo)
        st.divider()
        if st.button("Reportar ocorrência", use_container_width=True):
            try:
                exigir(u.perfil, "reportar")
                i = oc.abrir(conexao(), origem="operador", tipo="ocorrencia_reportada", usuario=u)
                st.toast(f"Ocorrência #{i} aberta")
                st.rerun()
            except SemPermissao as erro:
                st.error(str(erro))


# ---------------------------------------------------------------- Saúde
def pagina_saude(u: au.Usuario) -> None:
    st.subheader("Ocorrências confirmadas pelo Trânsito")
    r = risco_agora(datetime.now(m.FUSO).replace(minute=0, second=0, microsecond=0).isoformat())
    if r:
        st.caption(f"Risco agora no local: **{r['nivel']}** ({r['probabilidade_atropelamento_1h']:.2%} de atropelamento "
                   "em 1 h, modelo do notebook 06).")
    lista = oc.listar(conexao(), ["confirmada", "despachada"])
    if not lista:
        st.caption("Nenhuma ocorrência confirmada no momento.")
    for o in lista:
        card_ocorrencia(o, "alerta" if o["estado"] == "confirmada" else "ambar")
        if o["estado"] == "confirmada":
            if st.button("Despachar ambulância (SIMULADA)", key=f"desp{o['id']}", type="primary"):
                executar("despachar", u, o["id"])
        elif st.button("Encerrar atendimento", key=f"enc{o['id']}"):
            executar("encerrar", u, o["id"])
    st.caption("Despachar manda ao nó da faixa a aproximação da ambulância SIMULADA (600 m a 40 km/h): ele dá "
               "prioridade a ela. Não há integração com o SAMU.")


# ---------------------------------------------------------------- Gestão
def tabela_ocorrencias() -> pd.DataFrame:
    linhas = []
    con = conexao()
    for o in oc.listar(con):
        t = oc.tempos(con, o["id"])

        def seg(a, b):
            if a in t and b in t:
                return int((datetime.fromisoformat(t[b]["timestamp"]) -
                            datetime.fromisoformat(t[a]["timestamp"])).total_seconds())
            return None
        linhas.append({"#": o["id"], "tipo": oc.TIPOS.get(o["tipo"], o["tipo"]), "origem": o["origem"],
                       "estado": o["estado"], "aberta": _ts(o["aberta_em"]),
                       "até confirmar (s)": seg("pendente", "confirmada"),
                       "até despachar (s)": seg("confirmada", "despachada"),
                       "atendimento (s)": seg("despachada", "encerrada"),
                       "descarte": (t.get("descartada") or {}).get("motivo")})
    return pd.DataFrame(linhas)


def pagina_painel() -> None:
    spec = importlib.util.spec_from_file_location("painel_betterway", RAIZ / "src" / "dashboard" / "app.py")
    painel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(painel)
    painel.render_painel()


def pagina_estudo_a() -> None:
    st.subheader("Estudo A — o cruzamento sem e com a BetterWay (SUMO)")
    st.caption("RESULTADOS ESPERADOS de simulação: cruzamento sintético calibrado pelo piloto; fluxos estimados.")
    for nome, legenda in [("animacao_pedestre.gif", "Pessoa com mobilidade reduzida: o verde do pedestre é estendido "
                                                    "até ela terminar"),
                          ("animacao_ambulancia.gif", "Ambulância: prioridade só com a faixa vazia")]:
        p = EVID / "estudo_a" / nome
        if p.exists():
            st.image(str(p), caption=legenda, use_container_width=True)
    p = EVID / "estudo_a" / "estudo_a_resumo.csv"
    if p.exists():
        st.dataframe(pd.read_csv(p, sep=";", encoding="utf-8-sig"), hide_index=True, use_container_width=True)


def pagina_clipes() -> None:
    st.subheader("Avaliação nos clipes SINTÉTICOS (Veo 3)")
    st.caption("Clipes gerados por IA, com gabarito pelo nome do arquivo. Mostram a regra funcionando, não medem "
               "desempenho no mundo real — por isso ficam separados dos resultados com vídeo real.")
    p = EVID / "operador" / "avaliacao_clipes.csv"
    if not p.exists():
        st.info("Avaliação ainda não gerada (`python src/visao/processar_clipes.py`).")
        return
    df = pd.read_csv(p, sep=";", encoding="utf-8-sig")
    st.metric("Clipes com o resultado esperado", f"{int(df.acerto.sum())}/{len(df)}")
    st.dataframe(df, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------- sala de controle
def pagina_sala(u: au.Usuario) -> None:
    st.subheader("Sala de controle — nó da faixa (Largo da Concórdia)")
    no = no_ao_vivo()

    @st.fragment(run_every=3)
    def estado():
        c1, c2, c3 = st.columns(3)
        e = no.estado or {}
        c1.metric("Modo do nó", cam.NOMES_MODO.get(e.get("modo"), "sem sinal"))
        c2.metric("Fase do semáforo", (e.get("fase") or "—").replace("_", " "))
        c3.metric("Broker MQTT", "conectado" if no.conectado else "desconectado")
        if no.estado_recebido_em:
            st.caption(f"Último estado recebido às {no.estado_recebido_em:%H:%M:%S} (retido no broker).")
        r = risco_agora(datetime.now(m.FUSO).replace(minute=0, second=0, microsecond=0).isoformat())
        if r:
            st.caption(f"Risco agora: **{r['nivel']}** ({r['probabilidade_atropelamento_1h']:.2%} em 1 h).")
        if no.eventos:
            st.dataframe(pd.DataFrame(list(no.eventos))[["recebido_em", "tipo"]], hide_index=True,
                         use_container_width=True)
    estado()

    if pode(u.perfil, "cenario"):
        st.markdown("**Mandar cenário ao nó** (comando MQTT no mesmo contrato da central)")
        st.caption("Não use junto com `central.py`: os comandos dos dois se misturariam no nó.")
        cols = st.columns(len(CENARIOS))
        for col, nome in zip(cols, CENARIOS):
            if col.button(ROTULOS_CENARIO[nome], key=f"cen_{nome}", use_container_width=True):
                try:
                    exigir(u.perfil, "cenario")
                    ok = no.publicar(comando_cenario(nome))
                    st.toast(f"Cenário {nome}: {'enviado' if ok else 'não enviado (broker desconectado)'}")
                except SemPermissao as erro:
                    st.error(str(erro))
    else:
        st.caption("Seu perfil acompanha o nó; só o Trânsito manda cenários.")


# ---------------------------------------------------------------- principal
def main() -> None:
    st.set_page_config(page_title="BetterWay — operação", page_icon="🚦", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f"<div class='bw-aviso'>{AVISO}</div>", unsafe_allow_html=True)
    u = usuario_da_sessao()
    if u is None:
        tela_login()
        return
    with st.sidebar:
        st.markdown(f"### BetterWay\n**{u.nome}**  \nPerfil: {PERFIS[u.perfil]}")
        pagina = st.radio("Tela", PAGINAS[u.perfil], label_visibility="collapsed")
        if st.button("Sair", use_container_width=True):
            au.registrar_acesso(conexao(), u.usuario, "saida")
            st.session_state.clear()
            st.rerun()
    if pagina == "Câmera e ocorrências":
        pagina_transito(u)
    elif pagina == "Ocorrências confirmadas":
        pagina_saude(u)
    elif pagina == "Painel":
        pagina_painel()
    elif pagina == "Ocorrências":
        st.subheader("Ocorrências e tempo de cada etapa")
        df = tabela_ocorrencias()
        if df.empty:
            st.caption("Nenhuma ainda.")
        else:
            st.dataframe(df.astype(object).where(df.notna(), "—"), hide_index=True, use_container_width=True)
    elif pagina == "Estudo A (SUMO)":
        pagina_estudo_a()
    elif pagina == "Clipes sintéticos":
        pagina_clipes()
    else:
        pagina_sala(u)


main()
