"""Estilo da interface BetterWay: tokens do kit de marca (v2), CSS global e peças em HTML (cartões, selos, ícones).

Tokens: grafite #1A1D21 (surface), #2A2E33 (surface-raised), fundo-claro #F4F4EF (ink), #9AA1AA (ink-muted),
verde-betterway #00C27A (destaque), verde-escuro #006B44, âmbar #FFB000 (atenção), alerta #E63946 / #FF6B6B (risco).
Cor sempre acompanhada de palavra ou ícone (acessibilidade do kit).
"""
from __future__ import annotations

import html

VERDE, VERDE_ESC, GRAFITE = "#00C27A", "#006B44", "#1A1D21"
# cores que mudam com o tema (claro ou escuro): ver tokens()
CARTAO, CLARO, MUTED, DESTAQUE = "var(--bw-cartao)", "var(--bw-texto)", "var(--bw-muted)", "var(--bw-destaque)"
AMBAR, ALERTA, ALERTA_INK = "#FFB000", "#E63946", "var(--bw-alerta-texto)"

TEMAS = {
    "escuro": {"fundo": "#1A1D21", "cartao": "#24282D", "cartao-2": "#1E2125", "menu": "#2A2E33", "borda": "#33383F",
               "texto": "#F4F4EF", "texto-2": "#D9DAD5", "muted": "#A3AAB2", "trilho": "#4A5058",
               "destaque": "#00C27A", "alerta-texto": "#FF6B6B", "ambar-texto": "#FFB000", "chip": "#1F3A2F",
               "sombra": "0 1px 0 rgba(255,255,255,.03) inset", "vidro": "none"},
    "claro": {"fundo": "#E4E7E2", "cartao": "rgba(255,255,255,.80)", "cartao-2": "#F2F3F0", "menu": "#FFFFFF",
              "borda": "rgba(26,29,33,.09)", "texto": "#1A1D21", "texto-2": "#353B42", "muted": "#5A6169",
              "trilho": "#D3D7D0", "destaque": "#00804F", "alerta-texto": "#C62834", "ambar-texto": "#8A5A00",
              "chip": "#E2F4EA", "sombra": "0 1px 2px rgba(26,29,33,.04), 0 10px 30px rgba(26,29,33,.06)",
              "vidro": "blur(14px)"},
}


def cor(nome: str, tipo: str | None) -> str:
    """Cor real (hex) de um token, para quem não entende variáveis CSS (gráficos do Altair/Vega)."""
    return TEMAS["claro" if tipo == "light" else "escuro"][nome]


def tokens(tipo: str | None) -> str:
    """Variáveis CSS do tema: "light" usa o claro; qualquer outro valor, o escuro (o padrão da marca)."""
    t = TEMAS["claro" if tipo == "light" else "escuro"]
    return "<style>:root{" + "".join(f"--bw-{k}:{v};" for k, v in t.items()) + "}</style>"


def superficie(icone_nome: str | None, titulo: str, corpo: str, classe: str = "") -> str:
    """Cartão com ícone em círculo, título e conteúdo (HTML já escapado)."""
    chip = f'<span class="bw-chip">{icone(icone_nome, DESTAQUE, 22)}</span>' if icone_nome else ""
    return (f'<section class="bw-sup {classe}"><div class="bw-sup-topo">{chip}<h3>{esc(titulo)}</h3></div>'
            f'{corpo}</section>')

CSS = f"""
<style>
html {{ font-size: 17px; }}
.block-container {{ max-width: 1440px !important; padding: 4.25rem 2.75rem 3.5rem !important; }}
[data-testid="stHeaderLogo"], [data-testid="stLogo"] {{ height: 2.5rem !important; max-height: 2.5rem !important; }}
.stApp, [data-testid="stAppViewContainer"] {{ background: var(--bw-fundo) !important; color: var(--bw-texto); }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp label, .stApp li, [data-testid="stMarkdownContainer"] p,
[data-testid="stWidgetLabel"] p, [data-testid="stExpander"] summary p {{ color: var(--bw-texto); }}
.stApp h1 {{ font-size: 2.35rem !important; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: var(--bw-muted) !important;
  font-size: .95rem !important; }}
[data-testid="stHeader"] a, [data-testid="stHeader"] a span {{ color: var(--bw-texto) !important; }}
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div,
.stApp input, .stApp textarea, [data-testid="stTextInputRootElement"] {{ background: var(--bw-cartao-2) !important;
  color: var(--bw-texto) !important; border-color: var(--bw-borda) !important; }}
[data-baseweb="select"] span, [data-baseweb="select"] div {{ color: var(--bw-texto); }}
[data-baseweb="popover"] > div, [data-baseweb="menu"], [role="listbox"], [data-testid="stPopoverBody"]
  {{ background: var(--bw-menu) !important; color: var(--bw-texto) !important; }}
[role="option"], [role="option"] * {{ color: var(--bw-texto) !important; }}
.stApp button[kind="secondary"], .stApp [data-testid="stBaseButton-secondary"], .stApp [data-testid="stPopoverButton"]
  {{ background: var(--bw-cartao); color: var(--bw-texto); border-color: var(--bw-borda); }}
.stApp button[kind="secondary"] p, .stApp [data-testid="stPopoverButton"] p {{ color: var(--bw-texto); }}
[data-testid="stExpander"] details {{ background: var(--bw-cartao); border-color: var(--bw-borda) !important;
  border-radius: 20px !important; }}
[data-testid="stCheckbox"] label span {{ border-color: var(--bw-trilho); }}
@media (max-width: 760px) {{ .block-container {{ padding: 2rem 1rem 2.5rem !important; }} }}
[data-testid="stHeader"] {{ background: var(--bw-fundo); border-bottom: 1px solid var(--bw-borda); }}
h1, h2, h3 {{ letter-spacing: -0.015em; }}
h1 {{ font-weight: 500 !important; }}
.stApp {{ background: var(--bw-fundo); }}
button[kind="primary"], button[kind="primaryFormSubmit"] {{ color: {GRAFITE} !important; font-weight: 600 !important; }}
button[kind="primary"] p, button[kind="primaryFormSubmit"] p {{ color: {GRAFITE} !important; font-weight: 600 !important; }}
.bw-login-espaco {{ height: 12vh; }}
@media (max-width: 760px) {{ .bw-login-espaco {{ height: 4vh; }} }}
.bw-hero {{ position: relative; overflow: hidden; border-radius: 20px; background: {CARTAO};
           padding: 48px 44px; margin: 12px 0 28px; }}
.bw-hero::after {{ content: ""; position: absolute; right: -60px; top: 0; bottom: 0; width: 42%;
  background: repeating-linear-gradient(115deg, {VERDE} 0 18px, transparent 18px 44px, {VERDE_ESC} 44px 62px,
  transparent 62px 88px); opacity: .9; clip-path: polygon(28% 0, 100% 0, 100% 100%, 0 100%); }}
.bw-hero > div {{ position: relative; z-index: 1; max-width: 640px; }}
.bw-hero .chamada {{ font-size: clamp(30px, 4.2vw, 52px); line-height: 1.08; margin: 0 0 16px; font-weight: 700;
  color: {CLARO}; letter-spacing: -0.02em; }}
.bw-hero .chamada .fim {{ color: {DESTAQUE}; }}
.bw-hero p {{ font-size: 17px; line-height: 1.6; color: var(--bw-texto-2); margin: 0; max-width: 58ch; }}
@media (max-width: 760px) {{ .bw-hero {{ padding: 28px 22px 120px; }}
  .bw-hero::after {{ width: 100%; top: auto; height: 96px; right: 0; clip-path: none; }} }}
.bw-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin: 4px 0 28px; }}
.bw-card {{ background: {CARTAO}; border-radius: 24px; padding: 22px 24px; border: 1px solid var(--bw-borda);
  box-shadow: var(--bw-sombra); }}
.bw-card h3 {{ font-size: 19px; margin: 10px 0 6px; font-weight: 600; }}
.bw-card p {{ color: var(--bw-texto-2); font-size: 15px; line-height: 1.55; margin: 0; }}
.bw-card .verbo {{ color: {DESTAQUE}; font-weight: 600; font-size: 14px; }}
.bw-card .icone {{ color: {DESTAQUE}; }}
.bw-passos {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0; margin: 4px 0 28px;
             background: {CARTAO}; border-radius: 16px; border: 1px solid var(--bw-borda); overflow: hidden; }}
.bw-passo {{ padding: 20px 22px; border-right: 1px solid var(--bw-borda); }}
.bw-passo:last-child {{ border-right: 0; }}
.bw-passo b {{ display: block; font-size: 16px; margin: 8px 0 4px; }}
.bw-passo span {{ color: var(--bw-texto-2); font-size: 14px; line-height: 1.5; }}
.bw-passo .n {{ color: {DESTAQUE}; font-weight: 700; font-size: 14px; }}
.bw-secao {{ font-size: 1.35rem; font-weight: 600; margin: 8px 0 14px; color: var(--bw-texto); }}
.bw-nota {{ color: {MUTED}; font-size: 15px; line-height: 1.55; }}
.bw-kpi {{ background: {CARTAO}; border-radius: 22px; padding: 18px 20px; border: 1px solid var(--bw-borda);
  box-shadow: var(--bw-sombra); }}
.bw-kpi .r {{ color: {MUTED}; font-size: 14px; font-weight: 500; }}
.bw-kpi .v {{ font-size: 26px; font-weight: 700; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.bw-kpi .s {{ color: {MUTED}; font-size: 14px; margin-top: 2px; }}
.bw-leitura {{ border-radius: 24px; box-shadow: var(--bw-sombra); padding: 22px 24px; border: 1px solid var(--bw-borda); background: {CARTAO}; margin-bottom: 20px; }}
.bw-leitura.padrao {{ border-color: {ALERTA}; box-shadow: inset 0 0 0 1px {ALERTA}; }}
.bw-leitura.atencao {{ border-color: {AMBAR}; }}
.bw-leitura .topo {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
.bw-leitura .titulo {{ font-size: 21px; font-weight: 700; }}
.bw-ev {{ display: grid; grid-template-columns: 26px 140px 1fr auto; gap: 10px; align-items: baseline;
          padding: 10px 0; border-top: 1px solid var(--bw-borda); font-size: 15px; }}
.bw-ev .nome {{ font-weight: 600; }}
.bw-ev .fonte {{ color: {MUTED}; font-size: 14px; text-align: right; }}
@media (max-width: 760px) {{ .bw-ev {{ grid-template-columns: 22px 1fr; }} .bw-ev .fonte {{ text-align: left; grid-column: 2; }}
  .bw-ev .txt {{ grid-column: 2; }} }}
.bw-conclusao {{ margin-top: 12px; padding: 14px 16px; border-radius: 12px; background: var(--bw-cartao-2); font-size: 15px; }}
.bw-selo {{ display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 4px 12px;
            font-size: 14px; font-weight: 700; }}
.bw-selo.ok {{ background: {VERDE}; color: {GRAFITE}; }}
.bw-selo.atencao {{ background: {AMBAR}; color: {GRAFITE}; }}
.bw-selo.risco {{ background: transparent; color: {ALERTA_INK}; box-shadow: inset 0 0 0 1.5px {ALERTA_INK}; }}
.bw-selo.neutro {{ background: var(--bw-borda); color: {CLARO}; }}
.bw-demo-topo {{ display: flex; gap: 14px; align-items: flex-start; margin: 36px 0 14px; max-width: 80ch; }}
.bw-demo-topo .icone {{ margin-top: 2px; }}
.bw-demo-topo .verbo {{ color: {DESTAQUE}; font-weight: 600; font-size: 14px; }}
.bw-mosaico {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; margin: 12px 0 24px; }}
.bw-cam {{ margin: 0; border-radius: 20px; box-shadow: var(--bw-sombra); overflow: hidden; border: 1px solid var(--bw-borda); background: #000; }}
.bw-cam video {{ width: 100%; aspect-ratio: 16 / 9; object-fit: cover; display: block; }}
.bw-cam .sem {{ aspect-ratio: 16 / 9; display: grid; place-items: center; color: {MUTED}; background: {CARTAO}; }}
.bw-cam figcaption {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 10px 12px;
  background: {CARTAO}; font-size: 14px; }}
.bw-cam .vivo {{ color: {DESTAQUE}; font-weight: 700; }}
.bw-cam .sim {{ background: var(--bw-borda); color: var(--bw-texto-2); border-radius: 999px; padding: 2px 8px; font-weight: 600; }}
.bw-cam .onde {{ color: {MUTED}; width: 100%; }}
.bw-tempo {{ font-size: 14px; }}
.bw-tempo div {{ display: grid; grid-template-columns: 64px 1fr; gap: 10px; padding: 8px 0; border-top: 1px solid var(--bw-borda); }}
.bw-tempo .h {{ color: {MUTED}; font-variant-numeric: tabular-nums; }}
.st-key-leitor {{ position: fixed; top: 4px; right: 16px; width: 200px; height: 40px; z-index: 1000000; }}
.st-key-leitor iframe {{ height: 40px; }}
@media (max-width: 760px) {{ .st-key-leitor {{ top: auto; bottom: 12px; right: 12px; }} }}
/* superfícies: tudo que é conteúdo mora num cartão */
.bw-sup, [class*="st-key-sup_"] {{ background: var(--bw-cartao); border: 1px solid var(--bw-borda); border-radius: 28px;
  padding: 24px 26px; box-shadow: var(--bw-sombra); backdrop-filter: var(--bw-vidro); margin-bottom: 18px; }}
[class*="st-key-sup_"] {{ gap: .6rem; }}
.bw-sup-topo {{ display: flex; gap: 14px; align-items: center; margin-bottom: 12px; }}
.bw-sup h3, .bw-sup-topo h3 {{ font-size: 1.2rem; font-weight: 600; margin: 0; padding: 0; color: var(--bw-texto); }}
.bw-sup p {{ font-size: 1rem; line-height: 1.6; color: var(--bw-texto-2); margin: 0; max-width: 70ch; }}
.bw-chip {{ width: 46px; height: 46px; border-radius: 50%; background: var(--bw-chip); display: grid;
  place-items: center; flex: none; }}
.bw-grade {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 18px; margin-bottom: 18px; }}
.bw-grade .bw-sup {{ margin: 0; }}
.bw-passos2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; margin-bottom: 18px; }}
.bw-passos2 .bw-sup {{ margin: 0; }}
.bw-passos2 .n {{ color: var(--bw-muted); font-weight: 600; font-size: .9rem; margin-left: auto; white-space: nowrap; }}
.bw-abertura {{ position: relative; overflow: hidden; background: var(--bw-cartao); border: 1px solid var(--bw-borda);
  border-radius: 32px; padding: 24px 34px; box-shadow: var(--bw-sombra); backdrop-filter: var(--bw-vidro);
  margin: 0 0 18px; display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 26px;
  align-items: center; }}
.bw-abertura::after {{ content: ""; position: absolute; right: 0; top: 0; bottom: 0; width: 18px;
  background: repeating-linear-gradient(180deg, {VERDE} 0 16px, transparent 16px 30px); opacity: .9; }}
.bw-abertura .lema {{ font-size: clamp(1.6rem, 2.3vw, 2.25rem); font-weight: 700; letter-spacing: -0.02em;
  line-height: 1.1; margin: 10px 0 10px; color: var(--bw-texto); }}
.bw-abertura .lema span {{ color: {DESTAQUE}; }}
.bw-abertura p {{ font-size: 1.05rem; line-height: 1.6; color: var(--bw-texto-2); margin: 0; max-width: 56ch; }}
.bw-abertura ul {{ list-style: none; margin: 0; padding: 0 18px 0 0; display: grid; gap: 8px; align-content: center; }}
.bw-abertura li {{ display: grid; grid-template-columns: 46px 1fr; gap: 14px; align-items: center;
  background: var(--bw-cartao-2); border-radius: 18px; padding: 6px 14px 6px 6px; }}
.bw-abertura li b {{ display: block; font-size: 1rem; color: var(--bw-texto); }}
.bw-abertura li span.t {{ font-size: .92rem; color: var(--bw-muted); line-height: 1.4; }}
@media (max-width: 900px) {{ .bw-abertura {{ grid-template-columns: 1fr; padding: 24px; }} }}
[class*="st-key-vg_cena_"] {{ background: var(--bw-cartao); border: 1px solid var(--bw-borda); border-radius: 32px;
  padding: 24px 22px 18px; box-shadow: var(--bw-sombra); backdrop-filter: var(--bw-vidro); }}
.st-key-tema_btn {{ position: fixed; top: 6px; right: 228px; z-index: 1000000; width: auto; }}
.st-key-tema_btn button {{ width: 40px; height: 40px; min-height: 40px; padding: 0; border-radius: 50%;
  background: var(--bw-cartao) !important; border: 1px solid var(--bw-borda) !important; }}
.st-key-tema_btn button span {{ font-size: 22px; color: var(--bw-texto); }}
@media (max-width: 760px) {{ .st-key-tema_btn {{ top: auto; bottom: 12px; right: auto; left: 12px; }} }}
/* Câmeras: o cartão inteiro é clicável (botão transparente por cima, com foco visível no teclado) */
[class*="st-key-camcard_"] {{ position: relative; gap: 0; }}
[class*="st-key-camcard_"] .bw-cam {{ transition: border-color .15s ease-out, transform .15s ease-out; }}
[class*="st-key-camcard_"]:hover .bw-cam {{ border-color: {VERDE}; transform: translateY(-2px); }}
[class*="st-key-camcard_"] [class*="st-key-abrir_"] {{ position: absolute; inset: 0; z-index: 3; margin: 0; }}
[class*="st-key-camcard_"] [class*="st-key-abrir_"] div, [class*="st-key-camcard_"] [class*="st-key-abrir_"] button
  {{ width: 100%; height: 100%; }}
[class*="st-key-camcard_"] [class*="st-key-abrir_"] button {{ opacity: 0; cursor: pointer; border-radius: 14px; }}
[class*="st-key-camcard_"] [class*="st-key-abrir_"] button:focus-visible {{ opacity: 1; background: transparent;
  box-shadow: inset 0 0 0 3px {VERDE}; }}
[class*="st-key-camcard_"] [class*="st-key-abrir_"] button:focus-visible p {{ visibility: hidden; }}
/* Visão geral: um cenário por vez (vídeo + simulação), trocado pela seta */
.bw-vg-chamada {{ font-size: clamp(20px, 2.1vw, 28px); font-weight: 700; letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 14px; color: {CLARO}; }}
.bw-vg-chamada span {{ color: {DESTAQUE}; }}
.bw-vg-sub {{ font-size: 16px; line-height: 1.55; color: var(--bw-texto-2); margin: -6px 0 18px; max-width: 88ch; }}
.bw-vg-topo {{ display: flex; gap: 14px; align-items: flex-start; margin: 0 0 16px; }}
.bw-vg-topo .icone {{ margin-top: 2px; }}
.bw-vg-topo .verbo {{ color: {DESTAQUE}; font-weight: 600; font-size: .9rem; }}
.bw-vg-topo .titulo {{ font-size: 1.35rem; font-weight: 700; margin: 1px 0 4px; color: var(--bw-texto); }}
.bw-vg-topo p {{ font-size: 1rem; line-height: 1.5; color: var(--bw-texto-2); margin: 0; max-width: 80ch; }}
.bw-vg-video {{ border-radius: 24px; overflow: hidden; border: 1px solid var(--bw-borda); background: #000; aspect-ratio: 16 / 9; }}
.bw-vg-video video {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.bw-vg-video.vazio {{ background: {CARTAO}; display: grid; place-items: center; text-align: center; }}
.bw-vg-video.vazio > div {{ display: grid; justify-items: center; gap: 6px; padding: 16px; }}
.bw-vg-video.vazio b {{ font-size: 16px; color: var(--bw-texto-2); }}
.bw-vg-video.vazio span {{ color: {MUTED}; font-size: 13px; font-family: ui-monospace, monospace; }}
[class*="st-key-vg_cena_"] {{ animation: bw-entra .4s ease-out both; }}
@keyframes bw-entra {{ from {{ opacity: 0; transform: translateX(28px); }} to {{ opacity: 1; transform: none; }} }}
@media (prefers-reduced-motion: reduce) {{ [class*="st-key-vg_cena_"] {{ animation: none; }} }}
.stApp .st-key-vg_proximo button, .stApp .st-key-vg_anterior button {{ width: 50px; height: 50px; min-height: 50px;
  min-width: 50px; flex: none; border-radius: 50%; padding: 0;
  background: {VERDE} !important; border: 0 !important; color: {GRAFITE} !important; box-shadow: 0 6px 18px rgba(0, 194, 122, .28);
  transition: transform .15s ease-out; }}
.st-key-vg_anterior button:hover {{ transform: translateX(-3px); background: {VERDE}; color: {GRAFITE}; }}
.st-key-vg_proximo button:hover {{ transform: translateX(3px); background: {VERDE}; color: {GRAFITE}; }}
.stApp .st-key-vg_proximo button span, .stApp .st-key-vg_anterior button span {{ font-size: 30px; color: {GRAFITE}; }}
.st-key-vg_pontos {{ margin-top: 8px; }}
.st-key-vg_pontos [class*="st-key-vg_ponto_"] button {{ width: 14px; height: 14px; min-height: 14px; padding: 0;
  border-radius: 50%; background: var(--bw-trilho); border: 0; }}
.st-key-vg_pontos [class*="st-key-vg_ponto_"] button:disabled {{ background: {VERDE}; opacity: 1; width: 30px;
  border-radius: 7px; }}
.st-key-vg_pontos [class*="st-key-vg_ponto_"] button p {{ font-size: 0; }}
.bw-vg-conta {{ margin: 0 18px 0 6px; font-variant-numeric: tabular-nums; }}
</style>
"""

# ícones de contorno (traço 2, cantos arredondados — no estilo Lucide pedido pelo kit), 24×24
_IC = {
    "pedestre": '<circle cx="13" cy="4" r="2"/><path d="m9 20 3-6 3 3v4"/><path d="m6 12 3-4 4 1 3 3 3 1"/>',
    "vida": '<path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7Z"/><path d="M3.5 12h4l1.5-3 3 6 1.5-3h7"/>',
    "ambulancia": '<path d="M10 10H6M8 8v4"/><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M14 9h4l4 4v4a1 1 0 0 1-1 1h-2"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/><path d="M9 18h6"/>',
    "escudo": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
    "camera": '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3Z"/><circle cx="12" cy="13" r="3"/>',
    "rota": '<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
    "alerta": '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4M12 17h.01"/>',
    "ok": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "menos": '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
    "duvida": '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>',
    "semaforo": '<rect x="7" y="2" width="10" height="20" rx="3"/><circle cx="12" cy="7" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="12" cy="17" r="1.6"/>',
    "dados": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "cadeado": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "decide": '<path d="M12 3v3M12 18v3M3 12h3M18 12h3"/><circle cx="12" cy="12" r="5"/><path d="m10 12 1.5 1.5L14 11"/>',
    "pino": '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "grafico": '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>',
}


def icone(nome: str, cor: str = "currentColor", tamanho: int = 22) -> str:
    return (f'<svg width="{tamanho}" height="{tamanho}" viewBox="0 0 24 24" fill="none" style="stroke:{cor}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_IC[nome]}</svg>')


def esc(t) -> str:
    return html.escape(str(t))


SELO_NIVEL = {"padrao": ("risco", "alerta", "Padrão se repetindo"), "atencao": ("atencao", "alerta", "Atenção"),
              "normal": ("ok", "ok", "Normal")}
ICONE_EVIDENCIA = {"pesa": ("alerta", AMBAR), "nao_pesa": ("menos", MUTED), "sem_dado": ("duvida", MUTED)}


def selo_nivel(nivel: str) -> str:
    classe, ic, texto = SELO_NIVEL[nivel]
    return f'<span class="bw-selo {classe}">{icone(ic, "currentColor", 15)}{texto}</span>'


def kpi(rotulo: str, valor: str, sub: str = "") -> str:
    return (f'<div class="bw-kpi"><div class="r">{esc(rotulo)}</div><div class="v">{esc(valor)}</div>'
            f'<div class="s">{esc(sub)}</div></div>')
