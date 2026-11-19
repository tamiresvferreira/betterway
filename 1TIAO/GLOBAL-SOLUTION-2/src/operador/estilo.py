"""Estilo da interface BetterWay: tokens, CSS global e peças em HTML (cartões, selos, ícones).

Segue o sistema visual da skill landing-page-design (B1 a B9), com a fonte da marca (Montserrat):
- texto só em estilos com nome (heading, title, body, caption), todos na escala 12/14/16/18/20/24/30/36 px;
- espaçamentos só de 2, 4, 8, 12, 16, 24, 32, 40, 48, 64 px; cantos da escala (8, 12, 16, 24 px e círculo);
- fundos lisos (sem gradiente); no escuro, só #181818, #1F1F1F, #272727, #313131;
- uma curva de movimento (cubic-bezier(0.22, 1, 0.36, 1)), 500 ms para posição e 300 ms para cor;
- ícones Phosphor (icones.py). Cor sempre acompanhada de palavra ou ícone.
"""
from __future__ import annotations

import html
from urllib.parse import quote

from icones import ICONES

VERDE, VERDE_ESC, GRAFITE = "#00C27A", "#006B44", "#1A1D21"
# cores que mudam com o tema (claro ou escuro): ver tokens()
CARTAO, CLARO, MUTED, DESTAQUE = "var(--bw-cartao)", "var(--bw-texto)", "var(--bw-muted)", "var(--bw-destaque)"
AMBAR, ALERTA, ALERTA_INK = "#FFB000", "#E63946", "var(--bw-alerta-texto)"
CURVA = "cubic-bezier(0.22, 1, 0.36, 1)"

TEMAS = {
    "escuro": {"fundo": "#181818", "cartao": "#1F1F1F", "cartao-2": "#272727", "menu": "#272727", "borda": "#313131",
               "texto": "#F5F5F2", "texto-2": "#D4D4D0", "muted": "#A3A3A0", "trilho": "#3D3D3D",
               "destaque": "#00C27A", "alerta-texto": "#FF6B6B", "ambar-texto": "#FFB000", "chip": "#272727",
               "nav": "rgba(31,31,31,.72)",
               "sombra": "0 0 0 1px rgba(255,255,255,.08), 0 1px 0 rgba(255,255,255,.04) inset"},
    "claro": {"fundo": "#EEEFEC", "cartao": "#FFFFFF", "cartao-2": "#F5F6F3", "menu": "#FFFFFF", "borda": "#E1E3DE",
              "texto": "#1A1D21", "texto-2": "#3A4047", "muted": "#5F666E", "trilho": "#D5D8D2",
              "destaque": "#00804F", "alerta-texto": "#C62834", "ambar-texto": "#8A5A00", "chip": "#E6F5EC",
              "nav": "rgba(255,255,255,.72)",
              "sombra": "0 0 0 1px rgba(26,29,33,.06), 0 1px 2px -1px rgba(26,29,33,.08), 0 8px 24px rgba(26,29,33,.07)"},
}


def cor(nome: str, tipo: str | None) -> str:
    """Cor real (hex) de um token, para quem não entende variáveis CSS (gráficos do Altair/Vega)."""
    return TEMAS["claro" if tipo == "light" else "escuro"][nome]


def tokens(tipo: str | None) -> str:
    """Variáveis CSS do tema: "light" usa o claro; qualquer outro valor, o escuro (o padrão da marca)."""
    t = TEMAS["claro" if tipo == "light" else "escuro"]
    return "<style>:root{" + "".join(f"--bw-{k}:{v};" for k, v in t.items()) + "}</style>"


def icone(nome: str, cor: str = "currentColor", tamanho: int = 24) -> str:
    return (f'<svg width="{tamanho}" height="{tamanho}" viewBox="0 0 256 256" style="fill:{cor}" aria-hidden="true">'
            f'{ICONES[nome]}</svg>')


def icone_url(nome: str, cor_hex: str) -> str:
    """Ícone como imagem de fundo (para botões do Streamlit, que não aceitam SVG próprio)."""
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 256 256' fill='{cor_hex}'>{ICONES[nome]}</svg>"
    return f'url("data:image/svg+xml;utf8,{quote(svg)}")'


def esc(t) -> str:
    return html.escape(str(t))


def superficie(icone_nome: str | None, titulo: str, corpo: str, classe: str = "") -> str:
    """Cartão com ícone em círculo, título e conteúdo (HTML já escapado)."""
    chip = f'<span class="bw-chip">{icone(icone_nome, DESTAQUE, 24)}</span>' if icone_nome else ""
    return (f'<section class="bw-sup {classe}"><div class="bw-sup-topo">{chip}<h3>{esc(titulo)}</h3></div>'
            f'{corpo}</section>')


CSS = f"""
<style>
/* ---------- base: escala da skill (16 px), estilos de texto com nome ---------- */
html {{ font-size: 16px; -webkit-font-smoothing: antialiased; }}
.stApp, [data-testid="stAppViewContainer"] {{ background: var(--bw-fundo) !important; color: var(--bw-texto); }}
.block-container {{ max-width: 100% !important; padding: 96px 48px 64px !important; }}
@media (max-width: 760px) {{ .block-container {{ padding: 80px 16px 48px !important; }} }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {{ text-wrap: balance; letter-spacing: -0.01em; color: var(--bw-texto); }}
.stApp p, .stApp li {{ text-wrap: pretty; }}
.stApp h1 {{ font-size: 30px !important; line-height: 36px !important; font-weight: 600 !important; padding: 0 0 8px !important; }}
.stApp h2, .stApp h3 {{ font-size: 20px !important; line-height: 28px !important; font-weight: 600 !important; }}
.heading-3 {{ font-size: 36px; line-height: 40px; font-weight: 600; }}
.heading-4 {{ font-size: 30px; line-height: 36px; font-weight: 600; }}
.heading-5 {{ font-size: 24px; line-height: 32px; font-weight: 600; }}
.heading-6 {{ font-size: 20px; line-height: 28px; font-weight: 600; }}
.title-1 {{ font-size: 20px; line-height: 28px; font-weight: 500; }}
.title-2 {{ font-size: 18px; line-height: 28px; font-weight: 500; }}
.title-3 {{ font-size: 16px; line-height: 24px; font-weight: 500; }}
.body-2 {{ font-size: 16px; line-height: 24px; font-weight: 500; }}
.body-3 {{ font-size: 16px; line-height: 24px; font-weight: 400; }}
.caption-1 {{ font-size: 14px; line-height: 20px; font-weight: 500; }}
.caption-2 {{ font-size: 14px; line-height: 20px; font-weight: 400; }}
.stApp label, [data-testid="stMarkdownContainer"] p, [data-testid="stWidgetLabel"] p,
[data-testid="stExpander"] summary p {{ color: var(--bw-texto); }}
[data-testid="stMarkdownContainer"] p {{ font-size: 16px; line-height: 24px; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: var(--bw-muted) !important;
  font-size: 14px !important; line-height: 20px !important; }}
/* ---------- navegação: barra compacta, flutuante e translúcida ---------- */
[data-testid="stHeader"] {{ top: 12px !important; left: 16px !important; right: 16px !important; width: auto !important;
  height: 56px !important; border-radius: 9999px; background: var(--bw-nav) !important; border: 1px solid var(--bw-borda);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }}
[data-testid="stHeader"] a, [data-testid="stHeader"] a span, [data-testid="stHeader"] a p {{ color: var(--bw-texto) !important;
  font-size: 14px !important; font-weight: 500 !important; }}
[data-testid="stHeader"] a {{ border-radius: 9999px !important; transition: background-color 300ms {CURVA}; }}
[data-testid="stHeader"] a:hover {{ background: var(--bw-cartao-2) !important; }}
[data-testid="stHeader"] a[aria-current="page"] {{ background: var(--bw-cartao-2) !important; }}
[data-testid="stHeaderLogo"], [data-testid="stLogo"] {{ height: 32px !important; max-height: 32px !important; }}
/* ---------- campos, menus e botões do Streamlit seguindo o tema ---------- */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div,
.stApp input, .stApp textarea, [data-testid="stTextInputRootElement"] {{ background: var(--bw-cartao-2) !important;
  color: var(--bw-texto) !important; border-color: var(--bw-borda) !important; }}
[data-baseweb="select"] span, [data-baseweb="select"] div {{ color: var(--bw-texto); }}
[data-baseweb="popover"] > div, [data-baseweb="menu"], [role="listbox"], [data-testid="stPopoverBody"]
  {{ background: var(--bw-menu) !important; color: var(--bw-texto) !important; }}
[role="option"], [role="option"] * {{ color: var(--bw-texto) !important; }}
.stApp button {{ font-size: 16px; font-weight: 600; transition: transform 300ms {CURVA}, background-color 300ms {CURVA},
  border-color 300ms {CURVA}; }}
.stApp button:active {{ transform: scale(0.98); }}
.stApp button:focus-visible {{ outline: 2px solid {VERDE} !important; outline-offset: 2px; }}
.stApp button[kind="secondary"], .stApp [data-testid="stBaseButton-secondary"], .stApp [data-testid="stPopoverButton"]
  {{ background: var(--bw-cartao); color: var(--bw-texto); border-color: var(--bw-borda); }}
.stApp button[kind="secondary"]:hover, .stApp [data-testid="stPopoverButton"]:hover {{ background: var(--bw-cartao-2);
  border-color: var(--bw-trilho); color: var(--bw-texto); }}
.stApp button[kind="secondary"] p, .stApp [data-testid="stPopoverButton"] p {{ color: var(--bw-texto); }}
button[kind="primary"], button[kind="primaryFormSubmit"] {{ color: {GRAFITE} !important; }}
button[kind="primary"] p, button[kind="primaryFormSubmit"] p {{ color: {GRAFITE} !important; font-weight: 600 !important; }}
[data-testid="stExpander"] details {{ background: var(--bw-cartao); border-color: var(--bw-borda) !important;
  border-radius: 16px !important; box-shadow: var(--bw-sombra); }}
[data-testid="stCheckbox"] label span {{ border-color: var(--bw-trilho); }}
/* ---------- cartões (superfícies): conteúdo sempre num cartão ---------- */
.bw-sup, [class*="st-key-sup_"], .bw-kpi, .bw-leitura, .bw-card {{ background: var(--bw-cartao);
  border: 1px solid var(--bw-borda); border-radius: 24px; padding: 24px; box-shadow: var(--bw-sombra); }}
.bw-sup, [class*="st-key-sup_"] {{ margin-bottom: 24px; }}
[class*="st-key-sup_"] {{ gap: 12px; }}
.bw-sup-topo {{ display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }}
.bw-sup h3, .bw-sup-topo h3 {{ font-size: 20px !important; line-height: 28px !important; font-weight: 600 !important;
  margin: 0; padding: 0 !important; color: var(--bw-texto); }}
.bw-sup p {{ font-size: 16px; line-height: 24px; color: var(--bw-texto-2); margin: 0; max-width: 68ch; }}
.bw-chip {{ width: 48px; height: 48px; border-radius: 9999px; background: var(--bw-chip); display: grid;
  place-items: center; flex: none; }}
.bw-grade, .bw-passos2, .bw-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 24px;
  margin-bottom: 24px; }}
.bw-grade .bw-sup, .bw-passos2 .bw-sup {{ margin: 0; }}
@media (min-width: 1200px) {{ .bw-grade.cinco {{ grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 16px; }} }}
.bw-passos2 .n {{ color: var(--bw-muted); font-size: 14px; line-height: 20px; font-weight: 500; margin-left: auto;
  white-space: nowrap; }}
.bw-card h3 {{ font-size: 18px; line-height: 28px; margin: 12px 0 4px; font-weight: 600; }}
.bw-card p {{ color: var(--bw-texto-2); font-size: 16px; line-height: 24px; margin: 0; }}
.bw-card .icone {{ color: {DESTAQUE}; }}
.bw-secao {{ font-size: 24px; line-height: 32px; font-weight: 600; margin: 8px 0 16px; color: var(--bw-texto);
  text-wrap: balance; }}
.bw-nota {{ color: {MUTED}; font-size: 14px; line-height: 20px; }}
/* indicador: um número grande; quando o valor é uma frase, ela fica inteira num tamanho só */
.bw-kpi .r {{ color: {MUTED}; font-size: 14px; line-height: 20px; font-weight: 500; }}
.bw-kpi .v {{ font-size: 30px; line-height: 36px; font-weight: 600; margin-top: 8px; font-variant-numeric: tabular-nums;
  color: var(--bw-texto); }}
.bw-kpi .s {{ color: {MUTED}; font-size: 14px; line-height: 20px; margin-top: 4px; }}
.bw-kpi .frase {{ font-size: 18px; line-height: 28px; font-weight: 500; margin-top: 8px; color: var(--bw-texto); }}
.bw-kpi .frase .ponto {{ display: inline-block; width: 8px; height: 8px; border-radius: 9999px; margin-right: 8px;
  vertical-align: middle; background: var(--bw-trilho); }}
.bw-kpi .frase .ponto.ok {{ background: {VERDE}; }}
.bw-kpi .frase .ponto.alerta {{ background: {AMBAR}; }}
/* leitura da situação */
.bw-leitura {{ margin-bottom: 24px; }}
.bw-leitura.padrao {{ border-color: {ALERTA}; box-shadow: inset 0 0 0 1px {ALERTA}; }}
.bw-leitura.atencao {{ border-color: {AMBAR}; }}
.bw-leitura .topo {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
.bw-leitura .titulo {{ font-size: 20px; line-height: 28px; font-weight: 600; }}
.bw-ev {{ display: grid; grid-template-columns: 24px 140px 1fr auto; gap: 12px; align-items: baseline;
          padding: 12px 0; border-top: 1px solid var(--bw-borda); font-size: 16px; line-height: 24px; }}
.bw-ev .nome {{ font-weight: 600; }}
.bw-ev .fonte {{ color: {MUTED}; font-size: 14px; line-height: 20px; text-align: right; }}
@media (max-width: 760px) {{ .bw-ev {{ grid-template-columns: 24px 1fr; }} .bw-ev .fonte {{ text-align: left; grid-column: 2; }}
  .bw-ev .txt {{ grid-column: 2; }} }}
.bw-conclusao {{ margin-top: 16px; padding: 16px; border-radius: 12px; background: var(--bw-cartao-2); font-size: 16px;
  line-height: 24px; }}
.bw-selo {{ display: inline-flex; align-items: center; gap: 4px; border-radius: 9999px; padding: 4px 12px;
            font-size: 14px; line-height: 20px; font-weight: 600; }}
.bw-selo.ok {{ background: {VERDE}; color: {GRAFITE}; }}
.bw-selo.atencao {{ background: {AMBAR}; color: {GRAFITE}; }}
.bw-selo.risco {{ background: transparent; color: {ALERTA_INK}; box-shadow: inset 0 0 0 1.5px {ALERTA_INK}; }}
.bw-selo.neutro {{ background: var(--bw-cartao-2); color: {CLARO}; }}
/* câmeras */
.bw-mosaico {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin: 16px 0 24px; }}
.bw-cam {{ margin: 0; border-radius: 16px; overflow: hidden; border: 1px solid var(--bw-borda); background: #000;
  box-shadow: var(--bw-sombra); }}
.bw-cam video {{ width: 100%; aspect-ratio: 16 / 9; object-fit: cover; display: block; }}
.bw-cam .sem {{ aspect-ratio: 16 / 9; display: grid; place-items: center; color: {MUTED}; background: {CARTAO}; }}
.bw-cam figcaption {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 12px 16px;
  background: {CARTAO}; font-size: 14px; line-height: 20px; }}
.bw-cam .vivo {{ color: {DESTAQUE}; font-weight: 600; }}
.bw-cam .sim {{ background: var(--bw-cartao-2); color: var(--bw-texto-2); border-radius: 9999px; padding: 2px 8px; font-weight: 500; }}
.bw-cam .onde {{ color: {MUTED}; width: 100%; }}
[class*="st-key-camcard_"] {{ position: relative; gap: 0; }}
[class*="st-key-camcard_"] .bw-cam {{ transition: border-color 300ms {CURVA}, transform 500ms {CURVA}; }}
[class*="st-key-camcard_"]:hover .bw-cam {{ border-color: {VERDE}; transform: translateY(-2px); }}
[class*="st-key-camcard_"] [class*="st-key-abrir_"] {{ position: absolute; inset: 0; z-index: 3; margin: 0; }}
[class*="st-key-camcard_"] [class*="st-key-abrir_"] div, [class*="st-key-camcard_"] [class*="st-key-abrir_"] button
  {{ width: 100%; height: 100%; }}
[class*="st-key-camcard_"] [class*="st-key-abrir_"] button {{ opacity: 0; cursor: pointer; border-radius: 16px; }}
[class*="st-key-camcard_"] [class*="st-key-abrir_"] button:focus-visible {{ opacity: 1; background: transparent;
  box-shadow: inset 0 0 0 2px {VERDE}; }}
[class*="st-key-camcard_"] [class*="st-key-abrir_"] button:focus-visible p {{ visibility: hidden; }}
.bw-tempo {{ font-size: 14px; line-height: 20px; }}
.bw-tempo div {{ display: grid; grid-template-columns: 88px 1fr; gap: 12px; padding: 8px 0; border-top: 1px solid var(--bw-borda); }}
.bw-tempo .h {{ color: {MUTED}; font-variant-numeric: tabular-nums; }}
/* botões fixos do topo: leitura em voz e tema */
.st-key-leitor {{ position: fixed; top: 22px; right: 32px; width: 200px; height: 40px; z-index: 1000000; }}
.st-key-leitor iframe {{ height: 40px; }}
.st-key-tema_btn {{ position: fixed; top: 22px; right: 240px; z-index: 1000000; width: auto; gap: 0; }}
.st-key-tema_btn > div {{ margin: 0 !important; }}
.st-key-tema_btn button {{ width: 40px; height: 40px; min-height: 40px; padding: 0; border-radius: 9999px;
  background-color: var(--bw-cartao) !important; border: 1px solid var(--bw-borda) !important;
  background-repeat: no-repeat !important; background-position: center !important; background-size: 20px !important; }}
.st-key-tema_btn button:hover {{ background-color: var(--bw-cartao-2) !important; }}
@media (max-width: 760px) {{ .st-key-leitor {{ top: auto; bottom: 16px; right: 16px; }}
  .st-key-tema_btn {{ top: auto; bottom: 16px; right: auto; left: 16px; }} }}
/* ---------- Visão geral ---------- */
.bw-abertura {{ background: var(--bw-cartao); border: 1px solid var(--bw-borda); border-radius: 24px; padding: 16px 24px;
  margin: 0 0 16px; display: flex; gap: 24px; align-items: center; justify-content: space-between; flex-wrap: wrap;
  box-shadow: var(--bw-sombra); }}
.bw-abertura .lema {{ font-size: 24px; line-height: 32px; font-weight: 600; letter-spacing: -0.01em; margin: 0;
  color: var(--bw-texto); }}
.bw-abertura .lema span {{ color: {DESTAQUE}; }}
.bw-abertura p {{ font-size: 14px; line-height: 20px; color: var(--bw-muted); margin: 4px 0 0; max-width: 72ch; }}
.bw-abertura ul {{ list-style: none; margin: 0; padding: 0; display: flex; gap: 8px; flex-wrap: wrap; }}
.bw-abertura li {{ display: flex; gap: 8px; align-items: center; background: var(--bw-cartao-2); border-radius: 9999px;
  padding: 4px 16px 4px 4px; font-size: 14px; line-height: 20px; font-weight: 500; color: var(--bw-texto); }}
.bw-abertura li .bw-chip {{ width: 32px; height: 32px; }}
[class*="st-key-vg_cena_"] {{ background: var(--bw-cartao); border: 1px solid var(--bw-borda); border-radius: 24px;
  padding: 24px; box-shadow: var(--bw-sombra); animation: bw-entra 500ms {CURVA} both; }}
@keyframes bw-entra {{ from {{ opacity: 0; transform: translateX(24px); }} to {{ opacity: 1; transform: none; }} }}
@media (prefers-reduced-motion: reduce) {{ [class*="st-key-vg_cena_"] {{ animation: bw-aparece 300ms {CURVA} both; }} }}
@keyframes bw-aparece {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
.bw-vg-topo {{ display: flex; gap: 12px; align-items: flex-start; margin: 0 0 16px; }}
.bw-vg-topo {{ margin: 0; align-items: center; }}
.bw-vg-topo .verbo {{ color: {DESTAQUE}; font-size: 14px; line-height: 20px; font-weight: 600; margin-right: 12px; }}
.bw-vg-topo .titulo {{ font-size: 20px; line-height: 28px; font-weight: 600; margin: 0; color: var(--bw-texto); }}
.bw-vg-topo p {{ font-size: 14px; line-height: 20px; color: var(--bw-muted); margin: 2px 0 0; max-width: 110ch;
  text-wrap: pretty; }}
.bw-vg-video {{ border-radius: 16px; overflow: hidden; border: 1px solid var(--bw-borda); background: #000; aspect-ratio: 16 / 9;
  box-shadow: 0 12px 32px rgba(0,0,0,.18); }}
.bw-vg-video video {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.bw-vg-video.vazio {{ background: var(--bw-cartao-2); display: grid; place-items: center; text-align: center; }}
.bw-vg-video.vazio > div {{ display: grid; justify-items: center; gap: 8px; padding: 16px; }}
.bw-vg-video.vazio b {{ font-size: 16px; line-height: 24px; color: var(--bw-texto-2); }}
.bw-vg-video.vazio span {{ color: {MUTED}; font-size: 12px; line-height: 16px; }}
.stApp .st-key-vg_proximo button, .stApp .st-key-vg_anterior button {{ width: 48px; height: 48px; min-height: 48px;
  min-width: 48px; flex: none; border-radius: 9999px; padding: 0; background-color: {VERDE} !important; border: 0 !important;
  box-shadow: 0 4px 12px rgba(0, 194, 122, .28);
  background-repeat: no-repeat !important; background-position: center !important; background-size: 24px !important;
  transition: transform 500ms {CURVA}; }}
.stApp .st-key-vg_proximo button {{ background-image: {icone_url("seta_dir", GRAFITE)} !important; }}
.stApp .st-key-vg_anterior button {{ background-image: {icone_url("seta_esq", GRAFITE)} !important; }}
.stApp .st-key-vg_anterior button:hover {{ transform: translateX(-4px); }}
.stApp .st-key-vg_proximo button:hover {{ transform: translateX(4px); }}
.stApp .st-key-vg_proximo button p, .stApp .st-key-vg_anterior button p, .st-key-tema_btn button p {{ font-size: 0; }}
.st-key-vg_pontos {{ margin-top: 16px; }}
.st-key-vg_pontos [class*="st-key-vg_ponto_"] button {{ width: 12px; height: 12px; min-height: 12px; padding: 0;
  border-radius: 9999px; background: var(--bw-trilho); border: 0; }}
.st-key-vg_pontos [class*="st-key-vg_ponto_"] button:disabled {{ background: {VERDE}; opacity: 1; width: 32px; }}
.st-key-vg_pontos [class*="st-key-vg_ponto_"] button p {{ font-size: 0; }}
.bw-vg-conta {{ margin: 0 16px 0 8px; font-variant-numeric: tabular-nums; }}
.bw-login-espaco {{ height: 12vh; }}
@media (max-width: 760px) {{ .bw-login-espaco {{ height: 4vh; }} }}
@media (prefers-reduced-motion: reduce) {{ .stApp *, .stApp *::before {{ transition: none !important; }} }}
</style>
"""

SELO_NIVEL = {"padrao": ("risco", "alerta", "Padrão se repetindo"), "atencao": ("atencao", "alerta", "Atenção"),
              "normal": ("ok", "ok", "Normal")}
ICONE_EVIDENCIA = {"pesa": ("alerta", AMBAR), "nao_pesa": ("menos", MUTED), "sem_dado": ("duvida", MUTED)}


def selo_nivel(nivel: str) -> str:
    classe, ic, texto = SELO_NIVEL[nivel]
    return f'<span class="bw-selo {classe}">{icone(ic, "currentColor", 16)}{texto}</span>'


def kpi(rotulo: str, valor: str, sub: str = "", estado: str | None = None) -> str:
    """Indicador. Um número vira o destaque grande, com a explicação embaixo; um estado em palavras
    ("Conectada à central") fica como uma frase só, no tamanho do texto, com um ponto de cor (estado: ok/alerta)."""
    numero = bool(valor) and (valor[0].isdigit() or valor[0] in "+−-")
    if numero:
        return (f'<div class="bw-kpi"><div class="r">{esc(rotulo)}</div><div class="v">{esc(valor)}</div>'
                f'<div class="s">{esc(sub)}</div></div>')
    ponto = f'<span class="ponto {estado}"></span>' if estado else ""
    nota = f'<div class="s">{esc(sub)}</div>' if sub else ""
    return (f'<div class="bw-kpi"><div class="r">{esc(rotulo)}</div><div class="frase">{ponto}{esc(valor)}</div>'
            f'{nota}</div>')
