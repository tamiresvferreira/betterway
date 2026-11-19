"""Estilo da interface BetterWay: tokens do kit de marca (v2), CSS global e peças em HTML (cartões, selos, ícones).

Tokens: grafite #1A1D21 (surface), #2A2E33 (surface-raised), fundo-claro #F4F4EF (ink), #9AA1AA (ink-muted),
verde-betterway #00C27A (destaque), verde-escuro #006B44, âmbar #FFB000 (atenção), alerta #E63946 / #FF6B6B (risco).
Cor sempre acompanhada de palavra ou ícone (acessibilidade do kit).
"""
from __future__ import annotations

import html

VERDE, VERDE_ESC, GRAFITE, CARTAO = "#00C27A", "#006B44", "#1A1D21", "#2A2E33"
CLARO, MUTED, AMBAR, ALERTA, ALERTA_INK = "#F4F4EF", "#9AA1AA", "#FFB000", "#E63946", "#FF6B6B"

CSS = f"""
<style>
.block-container {{ max-width: 100% !important; padding: 2.75rem 2.5rem 3rem !important; }}
@media (max-width: 760px) {{ .block-container {{ padding: 2rem 1rem 2.5rem !important; }} }}
[data-testid="stHeader"] {{ background: {GRAFITE}; border-bottom: 1px solid #2F343A; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
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
.bw-hero .chamada .fim {{ color: {VERDE}; }}
.bw-hero p {{ font-size: 17px; line-height: 1.6; color: #D9DAD5; margin: 0; max-width: 58ch; }}
@media (max-width: 760px) {{ .bw-hero {{ padding: 28px 22px 120px; }}
  .bw-hero::after {{ width: 100%; top: auto; height: 96px; right: 0; clip-path: none; }} }}
.bw-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin: 4px 0 28px; }}
.bw-card {{ background: {CARTAO}; border-radius: 16px; padding: 20px 22px; border: 1px solid #343A41; }}
.bw-card h3 {{ font-size: 19px; margin: 10px 0 6px; font-weight: 600; }}
.bw-card p {{ color: #C9CBC6; font-size: 15px; line-height: 1.55; margin: 0; }}
.bw-card .verbo {{ color: {VERDE}; font-weight: 600; font-size: 14px; }}
.bw-card .icone {{ color: {VERDE}; }}
.bw-passos {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0; margin: 4px 0 28px;
             background: {CARTAO}; border-radius: 16px; border: 1px solid #343A41; overflow: hidden; }}
.bw-passo {{ padding: 20px 22px; border-right: 1px solid #343A41; }}
.bw-passo:last-child {{ border-right: 0; }}
.bw-passo b {{ display: block; font-size: 16px; margin: 8px 0 4px; }}
.bw-passo span {{ color: #C9CBC6; font-size: 14px; line-height: 1.5; }}
.bw-passo .n {{ color: {VERDE}; font-weight: 700; font-size: 14px; }}
.bw-secao {{ font-size: 22px; font-weight: 600; margin: 8px 0 12px; }}
.bw-nota {{ color: {MUTED}; font-size: 14px; line-height: 1.5; }}
.bw-kpi {{ background: {CARTAO}; border-radius: 16px; padding: 16px 18px; border: 1px solid #343A41; }}
.bw-kpi .r {{ color: {MUTED}; font-size: 14px; font-weight: 500; }}
.bw-kpi .v {{ font-size: 26px; font-weight: 700; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.bw-kpi .s {{ color: {MUTED}; font-size: 14px; margin-top: 2px; }}
.bw-leitura {{ border-radius: 20px; padding: 22px 24px; border: 1px solid #343A41; background: {CARTAO}; margin-bottom: 20px; }}
.bw-leitura.padrao {{ border-color: {ALERTA}; box-shadow: inset 0 0 0 1px {ALERTA}; }}
.bw-leitura.atencao {{ border-color: {AMBAR}; }}
.bw-leitura .topo {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
.bw-leitura .titulo {{ font-size: 21px; font-weight: 700; }}
.bw-ev {{ display: grid; grid-template-columns: 26px 140px 1fr auto; gap: 10px; align-items: baseline;
          padding: 10px 0; border-top: 1px solid #343A41; font-size: 15px; }}
.bw-ev .nome {{ font-weight: 600; }}
.bw-ev .fonte {{ color: {MUTED}; font-size: 14px; text-align: right; }}
@media (max-width: 760px) {{ .bw-ev {{ grid-template-columns: 22px 1fr; }} .bw-ev .fonte {{ text-align: left; grid-column: 2; }}
  .bw-ev .txt {{ grid-column: 2; }} }}
.bw-conclusao {{ margin-top: 12px; padding: 14px 16px; border-radius: 12px; background: #23272C; font-size: 15px; }}
.bw-selo {{ display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 4px 12px;
            font-size: 14px; font-weight: 700; }}
.bw-selo.ok {{ background: {VERDE}; color: {GRAFITE}; }}
.bw-selo.atencao {{ background: {AMBAR}; color: {GRAFITE}; }}
.bw-selo.risco {{ background: transparent; color: {ALERTA_INK}; box-shadow: inset 0 0 0 1.5px {ALERTA_INK}; }}
.bw-selo.neutro {{ background: #343A41; color: {CLARO}; }}
.bw-demo-topo {{ display: flex; gap: 14px; align-items: flex-start; margin: 36px 0 14px; max-width: 80ch; }}
.bw-demo-topo .icone {{ margin-top: 2px; }}
.bw-demo-topo .verbo {{ color: {VERDE}; font-weight: 600; font-size: 14px; }}
.bw-mosaico {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; margin: 12px 0 24px; }}
.bw-cam {{ margin: 0; border-radius: 14px; overflow: hidden; border: 1px solid #343A41; background: #000; }}
.bw-cam video {{ width: 100%; aspect-ratio: 16 / 9; object-fit: cover; display: block; }}
.bw-cam .sem {{ aspect-ratio: 16 / 9; display: grid; place-items: center; color: {MUTED}; background: {CARTAO}; }}
.bw-cam figcaption {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 10px 12px;
  background: {CARTAO}; font-size: 14px; }}
.bw-cam .vivo {{ color: {VERDE}; font-weight: 700; }}
.bw-cam .sim {{ background: #343A41; color: #C9CBC6; border-radius: 999px; padding: 2px 8px; font-weight: 600; }}
.bw-cam .onde {{ color: {MUTED}; width: 100%; }}
.bw-tempo {{ font-size: 14px; }}
.bw-tempo div {{ display: grid; grid-template-columns: 64px 1fr; gap: 10px; padding: 8px 0; border-top: 1px solid #343A41; }}
.bw-tempo .h {{ color: {MUTED}; font-variant-numeric: tabular-nums; }}
/* Visão geral: um cenário por vez (vídeo + simulação), trocado pela seta */
.bw-vg-chamada {{ font-size: clamp(20px, 2.1vw, 28px); font-weight: 700; letter-spacing: -0.02em; line-height: 1.15;
  margin: 0 0 14px; color: {CLARO}; }}
.bw-vg-chamada .fim {{ color: {VERDE}; }}
.bw-vg-topo {{ display: flex; gap: 12px; align-items: flex-start; margin: 0 0 12px; max-width: 92ch; }}
.bw-vg-topo .icone {{ margin-top: 2px; }}
.bw-vg-topo .verbo {{ color: {VERDE}; font-weight: 600; font-size: 13px; }}
.bw-vg-topo .titulo {{ font-size: 21px; font-weight: 700; margin: 1px 0 3px; }}
.bw-vg-topo p {{ font-size: 15px; line-height: 1.45; color: #D9DAD5; margin: 0; }}
.bw-vg-video {{ border-radius: 18px; overflow: hidden; border: 1px solid #343A41; background: #000; aspect-ratio: 16 / 9; }}
.bw-vg-video video {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.bw-vg-video.vazio {{ background: {CARTAO}; display: grid; place-items: center; text-align: center; }}
.bw-vg-video.vazio > div {{ display: grid; justify-items: center; gap: 6px; padding: 16px; }}
.bw-vg-video.vazio b {{ font-size: 16px; color: #D9DAD5; }}
.bw-vg-video.vazio span {{ color: {MUTED}; font-size: 13px; font-family: ui-monospace, monospace; }}
[class*="st-key-vg_cena_"] {{ animation: bw-entra .4s ease-out both; }}
@keyframes bw-entra {{ from {{ opacity: 0; transform: translateX(28px); }} to {{ opacity: 1; transform: none; }} }}
@media (prefers-reduced-motion: reduce) {{ [class*="st-key-vg_cena_"] {{ animation: none; }} }}
.st-key-vg_proximo button {{ width: 56px; height: 56px; min-height: 56px; border-radius: 50%; padding: 0;
  background: {VERDE}; border: 0; color: {GRAFITE}; box-shadow: 0 6px 18px rgba(0, 194, 122, .28);
  transition: transform .15s ease-out; }}
.st-key-vg_proximo button:hover {{ transform: translateX(3px); background: {VERDE}; color: {GRAFITE}; }}
.st-key-vg_proximo button span {{ font-size: 30px; color: {GRAFITE}; }}
.st-key-vg_pontos {{ margin-top: 8px; }}
.st-key-vg_pontos [class*="st-key-vg_ponto_"] button {{ width: 14px; height: 14px; min-height: 14px; padding: 0;
  border-radius: 50%; background: #4A5058; border: 0; }}
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
    "pino": '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "grafico": '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>',
}


def icone(nome: str, cor: str = "currentColor", tamanho: int = 22) -> str:
    return (f'<svg width="{tamanho}" height="{tamanho}" viewBox="0 0 24 24" fill="none" stroke="{cor}" '
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
