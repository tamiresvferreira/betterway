"""Painel da BetterWay (antes Via Segura SP): mapa de risco, indicadores dos módulos e eventos/alertas ao vivo.

    streamlit run src/dashboard/app.py          (de 1TIAO/GLOBAL-SOLUTION-2)

Só LÊ o que já existe (banco e docs/evidencias/); não recalcula nada, para os números baterem com o PDF.
O banco pode ser trocado pela variável de ambiente VIA_SEGURA_DB.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

RAIZ = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("VIA_SEGURA_DB", RAIZ / "data" / "processed" / "seguranca_viaria.db"))
EVID = RAIZ / "docs" / "evidencias"
PILOTO = 139   # Largo da Concórdia (Av. Rangel Pestana)


def consultar(sql: str, params=()) -> pd.DataFrame | None:
    """Consulta somente leitura; None se o banco ou a tabela não existirem."""
    if not DB.exists():
        return None
    try:
        with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as con:
            return pd.read_sql_query(sql, con, params=params)
    except (sqlite3.Error, pd.errors.DatabaseError):
        return None


def imagem(rel: str, legenda: str):
    p = EVID / rel
    if p.exists():
        st.image(str(p), caption=legenda, use_container_width=True)
    else:
        st.caption(f"(arquivo não encontrado: {rel})")


def tabela(rel: str, **kw):
    p = EVID / rel
    if p.exists():
        st.dataframe(pd.read_csv(p, sep=";", encoding="utf-8-sig", **kw), hide_index=True, use_container_width=True)
    else:
        st.caption(f"(arquivo não encontrado: {rel})")


def render_painel():
    """Mapa de risco, indicadores e eventos/alertas (também usado na tela de Gestão da interface do operador)."""
    if not DB.exists():
        st.warning(f"Banco não encontrado em {DB}. Gere-o com os notebooks 03 e 04 (src/estudo_b_risco_vida/).")

    aba_mapa, aba_ind, aba_ev = st.tabs(["Mapa de risco", "Indicadores", "Eventos e alertas"])

    # ---------------------------------------------------------------- 1. mapa
    with aba_mapa:
        cl = consultar("SELECT * FROM clusters")
        if cl is None or cl.empty:
            st.info("Sem grupos de atropelamentos no banco.")
        else:
            st.markdown("**Grupos de atropelamentos (DBSCAN, Infosiga-SP).** Tamanho = peso (fatal vale 3); vermelho = "
                        "50 primeiros do ranking urbano; o anel destaca o piloto, **Largo da Concórdia**.")
            cl = cl.assign(raio=(cl["peso"].clip(lower=1) ** 0.5) * 90,
                           top50=cl["rank_urbano"].fillna(9999) <= 50,
                           rotulo=cl["via_principal"].fillna("—"))
            cl["cor"] = cl["top50"].map({True: [215, 48, 39, 190], False: [42, 120, 214, 120]})
            piloto = cl[cl["cluster_id"] == PILOTO]
            camadas = [pdk.Layer("ScatterplotLayer", cl, get_position="[lon_centro, lat_centro]", get_radius="raio",
                                 get_fill_color="cor", pickable=True, radius_min_pixels=3),
                       pdk.Layer("ScatterplotLayer", piloto, get_position="[lon_centro, lat_centro]", get_radius=260,
                                 filled=False, stroked=True, get_line_color=[235, 104, 52], line_width_min_pixels=4)]
            st.pydeck_chart(pdk.Deck(layers=camadas, initial_view_state=pdk.ViewState(latitude=-23.56, longitude=-46.63,
                                                                                        zoom=10.3),
                                     tooltip={"text": "{rotulo}\nranking urbano: {rank_urbano}\npeso: {peso} "
                                                      "({n_fatais} fatais)"}))
            cols = [c for c in ("rank_urbano", "via_principal", "n_nao_fatais", "n_fatais", "peso", "n_escolas_300m",
                                "n_semaforos_150m") if c in cl.columns]
            top = cl[cl["rank_urbano"].notna()].sort_values("rank_urbano").head(10)[cols]
            st.markdown("**10 primeiros do ranking urbano** (prioridade pelo índice da CET: extensão ÷ peso)")
            st.dataframe(top, hide_index=True, use_container_width=True)
            if not piloto.empty:
                p = piloto.iloc[0]
                st.caption(f"Piloto: {p['via_principal']} — {int(p['rank_urbano'])}º do ranking urbano, "
                           f"{int(p['n_nao_fatais'])} atropelamentos não fatais e {int(p['n_fatais'])} fatais no grupo.")

    # ---------------------------------------------------------------- 2. indicadores
    with aba_ind:
        st.subheader("Estudo B — risco à vida")
        c1, c2 = st.columns(2)
        with c1:
            imagem("estudo_b/06_risco_piloto_por_hora.png", "Risco de atropelamento no piloto por hora (modelo do notebook 06)")
        with c2:
            imagem("estudo_b/06_captura_calibracao.png", "Captura e calibração do modelo de risco")

        st.markdown("**Visão computacional** — vídeo de DEMONSTRAÇÃO (Cidade do México, Pexels), rostos e placas borrados")
        met = EVID / "estudo_b" / "07_metricas.csv"
        if met.exists():
            m = pd.read_csv(met, sep=";", encoding="utf-8-sig").set_index("métrica")["valor"]
            cols = st.columns(4)
            for col, (k, rot) in zip(cols, [("travessias concluídas", "Travessias concluídas"),
                                            ("velocidade mediana (m/s)", "Velocidade mediana (m/s)"),
                                            ("conflitos", "Conflitos veículo × pedestre"), ("bloqueios", "Bloqueios da faixa")]):
                if k in m:
                    col.metric(rot, f"{m[k]:g}")
        c1, c2 = st.columns([1, 2])          # o vídeo da faixa é vertical (1080 × 1920)
        with c1:
            imagem("estudo_b/07_faixa_anotada.gif", "Faixa anotada (pessoas na faixa em laranja; veículos em azul)")
        with c2:
            imagem("estudo_b/09_cadeirante_anotado.gif", "Pedestre com cadeira de rodas (modelo ajustado no Colab)")
        tabela("estudo_b/09_cobertura_cadeirante.csv")

        st.subheader("Nó ESP32 (Wokwi)")
        c1, c2 = st.columns([3, 2])
        with c1:
            ac = EVID / "esp32" / "aceitacao.md"
            if ac.exists():
                linhas = [l for l in ac.read_text(encoding="utf-8").splitlines() if l.startswith("|")]
                st.markdown("\n".join(linhas))
        with c2:
            imagem("esp32/no_esp32_ambulancia_botao_recusado.png", "Ambulância a 17 s: botão recusado ('PRIORIDADE AMBULANCIA')")

        st.subheader("Estudo A — fluidez e emissões (SUMO)")
        st.caption("RESULTADOS ESPERADOS de simulação: cruzamento sintético calibrado pelo do piloto; fluxos estimados.")
        imagem("estudo_a/estudo_a_comparacoes.png", "Sem × com o sistema (média de 5 sementes; traço = mínimo–máximo)")
        tabela("estudo_a/estudo_a_resumo.csv")

    # ---------------------------------------------------------------- 3. eventos e alertas (ao vivo)
    with aba_ev:
        origens = st.multiselect("Origem dos eventos", ["yolo", "esp32", "central"], default=["esp32", "yolo"])

        @st.fragment(run_every=5)
        def ao_vivo():
            st.caption("Atualiza a cada 5 s. Com `central.py` e o nó no Wokwi rodando, os alertas aparecem aqui.")
            al = consultar("SELECT timestamp, modo, motivo, ROUND(risco * 100, 3) AS risco_pct, enviado FROM alertas "
                           "ORDER BY id DESC LIMIT 50")
            st.markdown("**Alertas da central** (mudanças de modo do nó)")
            if al is None:
                st.info("Sem tabela de alertas no banco.")
            else:
                st.dataframe(al, hide_index=True, use_container_width=True)
            if origens:
                marcas = ",".join("?" * len(origens))
                ev = consultar(f"SELECT timestamp, origem, tipo, payload_json FROM eventos WHERE origem IN ({marcas}) "
                               "ORDER BY id DESC LIMIT 100", tuple(origens))
                st.markdown("**Eventos** (visão, nó ESP32, central)")
                if ev is None:
                    st.info("Sem tabela de eventos no banco.")
                else:
                    st.dataframe(ev, hide_index=True, use_container_width=True)

        ao_vivo()


if __name__ == "__main__":
    st.set_page_config(page_title="BetterWay", page_icon="🚦", layout="wide")
    st.title("BetterWay — painel")
    st.caption("Global Solution FIAP 2026.2 · piloto: Largo da Concórdia (Av. Rangel Pestana, São Paulo). "
               "Dados reais do Infosiga-SP; o que é simulado ou de demonstração está marcado (regra 8).")
    render_painel()
