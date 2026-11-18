"""Player do Estudo A: o mesmo cruzamento, hoje × com a BetterWay, tocando a simulação real do SUMO em SVG.

Os quadros vêm de `docs/evidencias/estudo_a/cena_<cena>.json` (gerado por
`python src/simulacao/animacao_estudo_a.py --json`): posição de cada carro, ambulância e pessoa a cada 0,2 s e o estado
do semáforo. As métricas das pílulas vêm de `estudo_a_resumo.csv` (média de 5 sementes), nunca de valores ilustrativos.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
EVID_A = RAIZ / "docs" / "evidencias" / "estudo_a"
CENAS = {"pedestre": "Pessoa com mobilidade reduzida", "ambulancia": "Ambulância"}


def _num(v: float, casas: int = 1) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def metricas(cena: str, resumo: pd.DataFrame) -> dict:
    """Texto das pílulas de cada lado e a nota de custo, a partir do resumo do estudo."""
    r = resumo[resumo.comparacao == cena].set_index("sistema")
    sem, com = r.loc["sem"], r.loc["com"]
    if cena == "pedestre":
        return {"rotulo": "Travessias de pessoas com mobilidade reduzida em que o sinal fechou no meio",
                "sem": f"{_num(sem.surpreendidos_reduzida_pct, 0)}%", "com": f"{_num(com.surpreendidos_reduzida_pct, 0)}%",
                "nota": f"Custo para os carros: atraso médio de {_num(sem.atraso_medio_carro_s)} s para "
                        f"{_num(com.atraso_medio_carro_s)} s."}
    return {"rotulo": "Tempo médio da ambulância para passar o cruzamento",
            "sem": f"{_num(sem.tempo_ambulancia_s)} s", "com": f"{_num(com.tempo_ambulancia_s)} s",
            "nota": f"Pior caso: {_num(sem.tempo_ambulancia_max_s_max, 0)} s para {_num(com.tempo_ambulancia_max_s_max, 0)} s. "
                    "O verde só abre para ela com a faixa vazia."}


def carregar(cena: str) -> tuple[dict, dict]:
    dados = json.loads((EVID_A / f"cena_{cena}.json").read_text(encoding="utf-8"))
    resumo = pd.read_csv(EVID_A / "estudo_a_resumo.csv", sep=";", encoding="utf-8-sig")
    return dados, metricas(cena, resumo)


def html_cruzamento(dados: dict, met: dict) -> str:
    payload = json.dumps({"dados": dados, "met": met}, ensure_ascii=False, separators=(",", ":"))
    return _MODELO.replace("__PAYLOAD__", payload)


_MODELO = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--grafite:#1A1D21;--cartao:#2A2E33;--fundo:#F4F4EF;--verde:#00C27A;--verde-esc:#006B44;--ambar:#FFB000;
--alerta:#E63946;--muted:#9AA1AA}
*{box-sizing:border-box}
body{margin:0;font-family:Montserrat,system-ui,sans-serif;color:var(--grafite);background:transparent}
.barra{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:0 0 12px}
.barra button{font:600 14px Montserrat,sans-serif;border:0;border-radius:999px;padding:9px 18px;cursor:pointer;
background:var(--grafite);color:var(--fundo)}
.barra button.sec{background:#E4E4DD;color:var(--grafite)}
.barra button:focus-visible{outline:3px solid var(--verde);outline-offset:2px}
.barra input[type=range]{flex:1;min-width:140px;accent-color:var(--verde-esc)}
.relogio{font:600 14px Montserrat,sans-serif;font-variant-numeric:tabular-nums;min-width:72px;text-align:right}
.lados{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:760px){.lados{grid-template-columns:1fr}}
.lado{background:var(--grafite);border-radius:20px;overflow:hidden;box-shadow:0 10px 30px rgba(26,29,33,.18)}
.topo{display:flex;align-items:center;gap:10px;padding:14px 18px;font-weight:700;font-size:17px;color:var(--fundo)}
.lado.com .topo{background:var(--verde);color:var(--grafite)}
.selo{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-size:15px;flex:none;
background:rgba(244,244,239,.14)}
.lado.com .selo{background:var(--grafite);color:var(--verde)}
.sub{font-weight:500;font-size:13px;opacity:.75;margin-left:auto}
.mapa{position:relative}
svg{display:block;width:100%;height:auto}
.sinais{position:absolute;top:10px;left:10px;display:flex;flex-direction:column;gap:6px}
.sinal{display:flex;align-items:center;gap:8px;background:rgba(26,29,33,.78);backdrop-filter:blur(6px);
color:var(--fundo);border-radius:999px;padding:5px 12px 5px 8px;font-size:12px;font-weight:600}
.luz{width:10px;height:10px;border-radius:50%}
.aviso{margin:12px 16px 0;min-height:42px;border-radius:12px;padding:10px 14px;font-weight:700;font-size:14px;
color:var(--grafite);text-align:center;transition:opacity .25s,background-color .25s;opacity:0}
.pilula{margin:14px 16px 16px;border-radius:14px;padding:12px 16px;background:var(--cartao);color:var(--fundo);
display:flex;align-items:baseline;gap:12px}
.lado.com .pilula{background:rgba(0,194,122,.16)}
.pilula b{font-size:30px;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
.lado.sem .pilula b{color:#FF6B74}
.lado.com .pilula b{color:var(--verde)}
.pilula span{font-size:13px;color:var(--muted);line-height:1.35}
.pe{margin-top:12px;font-size:13px;color:#5A6068;line-height:1.5}
.giro{animation:giro .5s steps(1) infinite}
@keyframes giro{50%{fill:#2F6BFF}}
.pulso{animation:pulso 1.4s ease-out infinite;transform-box:fill-box;transform-origin:center}
@keyframes pulso{0%{opacity:.7;transform:scale(1)}100%{opacity:0;transform:scale(2.6)}}
@media (prefers-reduced-motion:reduce){.giro,.pulso{animation:none}}
</style></head><body>
<div class="barra">
  <button id="play">Pausar</button><button id="reset" class="sec">Recomeçar</button>
  <button id="vel" class="sec">Velocidade 1×</button>
  <input id="linha" type="range" min="0" value="0" step="1" aria-label="Momento da simulação">
  <div class="relogio" id="relogio">0,0 s</div>
</div>
<div class="lados">
  <section class="lado sem"><div class="topo"><span class="selo">✕</span>Hoje<span class="sub">semáforo de tempo fixo</span></div>
    <div class="mapa"><svg id="svg-sem" viewBox="-30 -21 60 42" role="img" aria-label="Cruzamento hoje"></svg>
      <div class="sinais" id="sinais-sem"></div></div><div class="aviso" id="aviso-sem" aria-live="polite"></div>
    <div class="pilula"><b id="met-sem"></b><span id="rot-sem"></span></div></section>
  <section class="lado com"><div class="topo"><span class="selo">✓</span>Com a BetterWay<span class="sub">semáforo que reage</span></div>
    <div class="mapa"><svg id="svg-com" viewBox="-30 -21 60 42" role="img" aria-label="Cruzamento com a BetterWay"></svg>
      <div class="sinais" id="sinais-com"></div></div><div class="aviso" id="aviso-com" aria-live="polite"></div>
    <div class="pilula"><b id="met-com"></b><span id="rot-com"></span></div></section>
</div>
<div class="pe" id="pe"></div>
<script>
const {dados:D, met:M} = __PAYLOAD__;
const NS = "http://www.w3.org/2000/svg", G = D.geometria;
const COR = {verde:"#00C27A", ambar:"#FFB000", alerta:"#E63946"};
const CARROS = ["#E8EAED","#6E8FB8","#9AA1AA","#C9CDD2","#55606C","#3E6FA8"];
const el = (n, a={}, pai) => { const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); if (pai) pai.appendChild(e); return e; };
const pts = p => p.map(([x,y]) => `${x},${-y}`).join(" ");
const hash = s => [...s].reduce((h,c) => (h*31 + c.charCodeAt(0)) >>> 0, 7);

function cenario(svg){
  const defs = el("defs", {}, svg);
  const f = el("filter", {id:svg.id+"-brilho", x:"-50%", y:"-50%", width:"200%", height:"200%"}, defs);
  el("feGaussianBlur", {stdDeviation:"0.6"}, f);
  el("rect", {x:-40, y:-30, width:80, height:60, fill:"#20242A"}, svg);
  // quarteirões: prédios vistos de cima nos quatro cantos
  for (const sx of [-1,1]) for (const sy of [-1,1]) {
    const blocos = [[6.2,11.4,9.5,9],[16.6,11.4,6.5,5.5],[16.6,17.6,6.5,4],[24,11.4,7,10]];
    blocos.forEach(([x,y,w,h], i) => {
      const X = sx>0 ? x : -x-w, Y = sy>0 ? y : -y-h;
      el("rect", {x:X, y:Y, width:w, height:h, rx:.6, fill: i%2 ? "#2A2E33" : "#30353B", stroke:"#3A4047", "stroke-width":.15}, svg);
    });
    for (const [x,y,r] of [[6.4,10.9,1.1],[13,10.9,.9],[23.3,10.9,1.2]])
      el("circle", {cx:sx*x, cy:sy*y, r, fill:"#2E6B4F", opacity:.9}, svg);
  }
  G.calcadas.forEach(p => el("polygon", {points:pts(p), fill:"#3A4047"}, svg));
  G.pistas.forEach(p => el("polygon", {points:pts(p), fill:"#2C3036"}, svg));
  G.juncoes.forEach(p => el("polygon", {points:pts(p), fill:"#2C3036"}, svg));
  // marcas da avenida (3 faixas por sentido) e da rua
  for (const y of [-5.4,-2.7,2.7,5.4]) for (const s of [-1,1])
    el("line", {x1:s*7.4, x2:s*30, y1:y, y2:y, stroke:"#F4F4EF", "stroke-width":.14, "stroke-dasharray":"1.6 1.6", opacity:.35}, svg);
  for (const s of [-1,1]) {
    el("line", {x1:s*7.4, x2:s*30, y1:-.12, y2:-.12, stroke:"#FFB000", "stroke-width":.12, opacity:.7}, svg);
    el("line", {x1:s*7.4, x2:s*30, y1:.12, y2:.12, stroke:"#FFB000", "stroke-width":.12, opacity:.7}, svg);
    el("line", {x1:0, x2:0, y1:s*12.3, y2:s*30, stroke:"#F4F4EF", "stroke-width":.14, "stroke-dasharray":"1.6 1.6", opacity:.35}, svg);
  }
  const bordas = [];
  G.faixas.forEach(fx => {
    const [x0,y0] = fx.inicio, [x1,y1] = fx.fim, comp = Math.hypot(x1-x0, y1-y0), n = Math.round(comp);
    const ux = (x1-x0)/comp, uy = (y1-y0)/comp, w = fx.largura*.85;
    for (let k = 0; k < n; k += 2) {
      const cx = x0 + ux*(k+.5), cy = y0 + uy*(k+.5);
      const vert = Math.abs(uy) > Math.abs(ux);
      el("rect", {x: vert ? cx-w/2 : cx-.25, y: vert ? -cy-.25 : -cy-w/2, width: vert ? w : .5, height: vert ? .5 : w,
                  fill:"#F4F4EF", opacity:.55}, svg);
    }
    if (fx.avenida) bordas.push(el("polygon", {points:pts(fx.poligono), fill:"none", "stroke-width":.35, filter:`url(#${svg.id}-brilho)`}, svg));
  });
  // semáforos da avenida, nos quatro cantos
  const luzes = [];
  for (const [x,y] of [[-8,9],[8,-9],[-8,-9],[8,9]]) {
    el("rect", {x:x-.7, y:y-.7, width:1.4, height:1.4, rx:.35, fill:"#111417", stroke:"#3A4047", "stroke-width":.1}, svg);
    luzes.push(el("circle", {cx:x, cy:y, r:.45}, svg));
  }
  const rastro = el("polyline", {fill:"none", stroke:"#00C27A", "stroke-width":.8, "stroke-linecap":"round", opacity:.55}, svg);
  const camada = el("g", {}, svg);
  return {bordas, luzes, rastro, camada, objs:new Map(), trilha:[]};
}

function carro(g, tipo, cor, comp){
  if (tipo === "ambulancia") {
    el("rect", {x:-1, y:0, width:2, height:comp, rx:.45, fill:"#FFFFFF"}, g);
    el("rect", {x:-1, y:comp*.55, width:2, height:.35, fill:"#E63946"}, g);
    el("rect", {x:-.18, y:comp*.25, width:.36, height:1.3, fill:"#E63946"}, g);
    el("rect", {x:-.65, y:comp*.25+.47, width:1.3, height:.36, fill:"#E63946"}, g);
    el("rect", {x:-.85, y:1.05, width:1.7, height:.4, rx:.15, fill:"#E63946", class:"giro"}, g);
    el("rect", {x:-.8, y:.35, width:1.6, height:.5, rx:.2, fill:"#1A1D21", opacity:.85}, g);
    return;
  }
  el("rect", {x:-.9, y:0, width:1.8, height:comp, rx:.5, fill:cor}, g);
  el("rect", {x:-.75, y:.9, width:1.5, height:.75, rx:.25, fill:"#1A1D21", opacity:.75}, g);
  el("rect", {x:-.7, y:comp-1.35, width:1.4, height:.55, rx:.2, fill:"#1A1D21", opacity:.6}, g);
}

const lerp = (a,b,t) => a + (b-a)*t;
const lerpAng = (a,b,t) => { let d = ((b-a+540)%360)-180; return a + d*t; };

function desenhar(lado, ctx, f){
  const Q = D[lado], i = Math.min(Math.floor(f), Q.length-1), j = Math.min(i+1, Q.length-1), t = f - i;
  const qa = Q[i], qb = Q[j];
  const verdePed = qa.verde_ped, verdeAv = qa.verde_avenida;
  ctx.bordas.forEach(b => b.setAttribute("stroke", verdePed ? COR.verde : COR.alerta));
  ctx.luzes.forEach(l => { l.setAttribute("fill", verdeAv ? COR.verde : COR.alerta); });
  const prox = new Map(qb.carros.map(c => [c[0], c])), proxP = new Map(qb.pessoas.map(p => [p[0], p]));
  const vistos = new Set();
  let amb = null;
  for (const c of qa.carros) {
    const [id, x0, y0, a0, tipo, comp, vel] = c, n = prox.get(id) || c;
    const x = lerp(x0, n[1], t), y = lerp(y0, n[2], t), a = lerpAng(a0, n[3], t);
    let o = ctx.objs.get(id);
    if (!o) { o = el("g", {}, ctx.camada); carro(o, tipo, CARROS[hash(id) % CARROS.length], comp); ctx.objs.set(id, o);
      if (tipo === "ambulancia") { o.rotulo = el("text", {"font-size":1.5, "font-weight":700, fill:"#F4F4EF", "text-anchor":"middle",
        "paint-order":"stroke", stroke:"#1A1D21", "stroke-width":.45, "font-family":"Montserrat"}, ctx.camada); o.rotulo.textContent = "Ambulância"; } }
    o.setAttribute("transform", `translate(${x},${-y}) rotate(${a})`);
    if (o.rotulo) { o.rotulo.setAttribute("x", x); o.rotulo.setAttribute("y", -y - 2.6); amb = [x, -y]; }
    vistos.add(id);
  }
  for (const p of qa.pessoas) {
    const [id, x0, y0, tipo] = p, n = proxP.get(id) || p;
    const x = lerp(x0, n[1], t), y = lerp(y0, n[2], t), lenta = tipo === "pedestre_reduzida";
    let o = ctx.objs.get(id);
    if (!o) { o = el("g", {}, ctx.camada);
      if (lenta) { el("circle", {r:.9, fill:"none", stroke:"#FFB000", "stroke-width":.25, class:"pulso"}, o);
        el("circle", {r:.85, fill:"#FFB000", stroke:"#1A1D21", "stroke-width":.15}, o);
        const tx = el("text", {x:-1.4, y:.5, "font-size":1.35, "font-weight":700, fill:"#FFB000", "text-anchor":"end",
          "paint-order":"stroke", stroke:"#1A1D21", "stroke-width":.45, "font-family":"Montserrat"}, o); tx.textContent = "Mobilidade reduzida"; }
      else el("circle", {r:.55, fill:"#F4F4EF", stroke:"#1A1D21", "stroke-width":.12}, o);
      ctx.objs.set(id, o); }
    o.setAttribute("transform", `translate(${x},${-y})`);
    vistos.add(id);
  }
  for (const [id, o] of ctx.objs) if (!vistos.has(id)) { o.remove(); if (o.rotulo) o.rotulo.remove(); ctx.objs.delete(id); }
  // rastro de prioridade da ambulância (só com a BetterWay, com o verde aberto para ela)
  if (lado === "com" && amb && verdeAv) { ctx.trilha.push(amb); if (ctx.trilha.length > 40) ctx.trilha.shift(); }
  else if (!amb) ctx.trilha = [];
  ctx.rastro.setAttribute("points", ctx.trilha.map(p => p.join(",")).join(" "));
  const s = document.getElementById("sinais-" + lado);
  const ped = verdePed ? `verde${qa.verde_ped_s != null ? " há " + Math.round(qa.verde_ped_s) + " s" : ""}` : "vermelho";
  s.innerHTML = `<div class="sinal"><span class="luz" style="background:${verdePed?COR.verde:COR.alerta}"></span>Pedestre: ${ped}</div>` +
                `<div class="sinal"><span class="luz" style="background:${verdeAv?COR.verde:COR.alerta}"></span>Carros na avenida: ${verdeAv?"verde":"vermelho"}</div>`;
  const av = document.getElementById("aviso-" + lado);
  if (qa.aviso) { av.textContent = qa.aviso; av.style.background = qa.cor; av.style.color = qa.cor === "#e63946" ? "#fff" : "#1A1D21"; av.style.opacity = 1; }
  else av.style.opacity = 0;
}

const ctx = {sem: cenario(document.getElementById("svg-sem")), com: cenario(document.getElementById("svg-com"))};
document.getElementById("met-sem").textContent = M.sem; document.getElementById("met-com").textContent = M.com;
document.getElementById("rot-sem").textContent = M.rotulo; document.getElementById("rot-com").textContent = M.rotulo;
document.getElementById("pe").textContent = "Mesmo cruzamento, mesmas pessoas e os mesmos carros nos dois lados: muda só o semáforo. " +
  "Animação da simulação no SUMO; os números são a média de 5 rodadas. " + M.nota + " Resultado esperado de simulação.";
const N = D.sem.length, linha = document.getElementById("linha"); linha.max = N - 1;
const reduzido = matchMedia("(prefers-reduced-motion: reduce)").matches;
// começa 3 s antes de a personagem da cena (ambulância ou pessoa com mobilidade reduzida) aparecer
const temPersonagem = q => q.carros.some(c => c[4] === "ambulancia") || q.pessoas.some(p => p[3] === "pedestre_reduzida");
const F0 = Math.max(0, D.sem.findIndex(temPersonagem) - Math.round(3 / D.passo_s));
let f = F0, tocando = !reduzido, vel = 1, ultimo = null;
const playBtn = document.getElementById("play");
const rotPlay = () => playBtn.textContent = tocando ? "Pausar" : "Reproduzir";
rotPlay();
function quadro(){ for (const l of ["sem","com"]) desenhar(l, ctx[l], f);
  document.getElementById("relogio").textContent = ((f-F0)*D.passo_s).toFixed(1).replace(".", ",") + " s"; linha.value = Math.floor(f); }
function laco(ts){ if (tocando && ultimo != null) { f += (ts-ultimo)/1000/D.passo_s*vel; if (f >= N-1) { f = F0; ctx.com.trilha = []; } }
  ultimo = ts; quadro(); requestAnimationFrame(laco); }
playBtn.onclick = () => { tocando = !tocando; rotPlay(); };
document.getElementById("reset").onclick = () => { f = F0; ctx.com.trilha = []; };
document.getElementById("vel").onclick = e => { vel = vel === 1 ? 2 : vel === 2 ? 4 : 1; e.target.textContent = `Velocidade ${vel}×`; };
linha.oninput = () => { f = +linha.value; ctx.com.trilha = []; };
requestAnimationFrame(laco);
</script></body></html>"""
