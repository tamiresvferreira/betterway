"""Leitura em voz da página (acessibilidade para quem tem deficiência visual ou baixa visão).

Um botão "Ouvir esta página" lê, com a voz do próprio navegador (Web Speech API, pt-BR, sem serviço externo), o título
e os textos da página aberta, na ordem em que aparecem. Clicar de novo para. Nada é gravado nem enviado.
"""
from __future__ import annotations

# elementos lidos, na ordem da página; os textos de dentro de gráficos e vídeos (iframes) ficam de fora
SELETORES = ("h1, h2, h3, p, li, label, [data-testid='stCaptionContainer'], [data-testid='stExpander'] summary, "
             ".titulo, .verbo, .bw-kpi .r, .bw-kpi .v, .bw-kpi .s, .bw-sinal b, .bw-val, figcaption")

HTML = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600&display=swap" rel="stylesheet">
<style>
body{margin:0;background:transparent;display:flex;justify-content:flex-end;font-family:Montserrat,system-ui,sans-serif}
button{display:inline-flex;align-items:center;gap:8px;border:1px solid #3A4047;background:#2A2E33;color:#F4F4EF;
border-radius:999px;padding:7px 14px;font:600 13px Montserrat,system-ui,sans-serif;cursor:pointer}
button[aria-pressed=true]{background:#00C27A;color:#1A1D21;border-color:#00C27A}
button:focus-visible{outline:3px solid #00C27A;outline-offset:2px}
svg{width:18px;height:18px}
</style></head><body>
<button id="ouvir" type="button" aria-pressed="false" title="Lê em voz alta os textos desta página">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
 aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/></svg>
<span id="rot">Ouvir esta página</span></button>
<script>
const SEL = __SELETORES__;
const pai = window.parent, voz = pai.speechSynthesis, b = document.getElementById("ouvir"), rot = document.getElementById("rot");
function estado(lendo){ b.setAttribute("aria-pressed", lendo); rot.textContent = lendo ? "Parar leitura" : "Ouvir esta página"; }
function textos(){
  const raiz = pai.document.querySelector('[data-testid="stMain"]') || pai.document.body, vistos = new Set(), saida = [];
  raiz.querySelectorAll(SEL).forEach(el => {
    if (el.closest('[data-testid="stExpanderDetails"]') && !el.closest('details[open]')) return;
    const t = (el.innerText || "").replace(/\s+/g, " ").trim();
    if (t.length < 2 || vistos.has(t) || el.offsetParent === null) return;
    for (const v of vistos) if (v.includes(t)) return;
    vistos.add(t); saida.push(t);
  });
  return saida;
}
function ler(){
  if (!voz) { rot.textContent = "Seu navegador não lê em voz alta"; return; }
  voz.cancel();
  const vozPt = voz.getVoices().find(v => /pt[-_]BR/i.test(v.lang)) || voz.getVoices().find(v => /^pt/i.test(v.lang));
  const partes = textos();
  if (!partes.length) return;
  estado(true);
  partes.forEach((t, i) => {
    const u = new pai.SpeechSynthesisUtterance(t);
    u.lang = "pt-BR"; if (vozPt) u.voice = vozPt; u.rate = 1;
    if (i === partes.length - 1) { u.onend = () => estado(false); u.onerror = () => estado(false); }
    voz.speak(u);
  });
}
b.addEventListener("click", () => { if (voz && (voz.speaking || voz.pending)) { voz.cancel(); estado(false); } else ler(); });
estado(!!(voz && voz.speaking));
</script></body></html>"""


def html_botao() -> str:
    import json
    return HTML.replace("__SELETORES__", json.dumps(SELETORES))
