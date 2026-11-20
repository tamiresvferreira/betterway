"""Componentes visuais da plataforma BetterWay, em HTML/SVG (funções puras, testadas).

Regras do kit e da skill de dados: cor sempre com palavra ou ícone; verde = seguro, âmbar = atenção, vermelho = risco;
texto mínimo de 14 px; nada de tabela onde um desenho explica melhor.
"""
from __future__ import annotations

from datetime import datetime

from estilo import ALERTA, ALERTA_INK, AMBAR, CARTAO, MUTED, VERDE, esc, icone

# ---------------------------------------------------------------- semáforo do nó
_FASES = {  # fase do nó → (luz dos carros, luz do pedestre)
    "carros_verde": ("verde", "vermelho"), "carros_amarelo": ("amarelo", "vermelho"),
    "vermelho_total": ("vermelho", "vermelho"), "pedestre_verde": ("vermelho", "verde"),
    "pedestre_pisca": ("vermelho", "pisca"),
}
_COR_LUZ = {"vermelho": ALERTA, "amarelo": AMBAR, "verde": VERDE}


# figura do pedestre: parado (vermelho) e andando (verde), desenhadas numa caixa 24×24
_BONECO_PARADO = ('<circle cx="12" cy="4" r="2.4"/><path d="M9 8h6l.8 7h-2l-.4 7h-2.8l-.4-7h-2Z"/>')
_BONECO_ANDANDO = ('<circle cx="13" cy="4" r="2.4"/><path d="M11 8.2 8 11l-1.6 4 1.8.6 1.3-3.2 1.4-1L10 14.5 8 22h2.2'
                   'l1.8-6 2.1 2.6V22h2v-4.2l-2.3-3 .7-3.2 1.2 1.6 3.3.8.4-1.9-2.4-.6L15 8.6c-.6-.9-2.6-1.1-4-.4Z"/>')


def semaforo_svg(fase: str | None) -> str:
    """Os dois grupos focais da faixa, como na rua: o dos carros (3 luzes) e o do pedestre (boneco parado e andando),
    com a fase escrita numa frase. Sem resposta do nó, mostra um ciclo local de demonstração, marcado como tal."""
    carros, ped = _FASES.get(fase or "", (None, None))
    local = carros is None                       # sem o nó: ciclo animado só para ilustrar

    def luz(cx, cy, cor_nome, acesa, classe=""):
        cor = _COR_LUZ[cor_nome]
        aceso = (f'<circle cx="{cx}" cy="{cy}" r="17" fill="{cor}" class="aceso {classe}" '
                 f'style="opacity:{1 if acesa else 0}"/>')
        return (f'<path d="M{cx - 24} {cy - 20} Q{cx} {cy - 34} {cx + 24} {cy - 20}" fill="#0B0B0B"/>'
                f'<circle cx="{cx}" cy="{cy}" r="17" fill="#2A2A2A"/>{aceso}')

    def boneco(cx, cy, desenho, cor, acesa, classe=""):
        return (f'<g transform="translate({cx - 13},{cy - 13}) scale(1.08)" fill="{cor}" class="aceso {classe}" '
                f'style="opacity:{1 if acesa else .16}">{desenho}</g>')

    c_vm, c_am, c_vd = (("l-vm", "l-am", "l-vd") if local else ("", "", ""))
    p_vm, p_vd = (("p-vm", "p-vd") if local else ("pisca" if ped == "pisca" else "", ""))
    svg = (f'<svg viewBox="0 0 250 200" role="img" aria-label="Semáforo: carros {carros or "ciclo de demonstração"}, '
           f'pedestre {ped or "ciclo de demonstração"}" data-carros="{carros or "nenhum"}" '
           f'data-pedestre="{"vermelho" if ped == "pisca" else ped or "nenhum"}">'
           # carros: três luzes com pala
           f'<rect x="38" y="8" width="64" height="164" rx="16" fill="#141414" stroke="#313131"/>'
           + luz(70, 44, "vermelho", carros == "vermelho", c_vm) + luz(70, 92, "amarelo", carros == "amarelo", c_am)
           + luz(70, 140, "verde", carros == "verde", c_vd)
           + '<text x="70" y="192" text-anchor="middle" class="rot">Carros</text>'
           # pedestre: boneco parado (vermelho) e andando (verde)
           f'<rect x="150" y="42" width="64" height="116" rx="16" fill="#141414" stroke="#313131"/>'
           f'<circle cx="182" cy="76" r="20" fill="#202020"/><circle cx="182" cy="124" r="20" fill="#202020"/>'
           + boneco(182, 76, _BONECO_PARADO, ALERTA, ped in ("vermelho", "pisca"), p_vm)
           + boneco(182, 124, _BONECO_ANDANDO, VERDE, ped == "verde", p_vd)
           + '<text x="182" y="192" text-anchor="middle" class="rot">Pedestre</text></svg>')
    if local:
        legenda = ("<b>Aguardando o nó da faixa</b><span>Enquanto ele não responde, o desenho mostra um ciclo comum "
                   "de demonstração.</span>")
    else:
        frase_c = {"verde": "Carros passando no verde", "amarelo": "Carros no amarelo, parando",
                   "vermelho": "Carros parados no vermelho"}[carros]
        frase_p = {"verde": "pedestre atravessando no verde", "vermelho": "pedestre esperando no vermelho",
                   "pisca": "pedestre terminando a travessia (vermelho piscando)"}[ped]
        legenda = f"<b>{frase_c}</b><span>e {frase_p}.</span>"
    return f'<div class="bw-semaforo{" local" if local else ""}">{svg}<div class="leg">{legenda}</div></div>'


# ---------------------------------------------------------------- feed de eventos do nó
_EVENTOS_NO = {
    "cartao_lido": ("pedestre", "Cartão lido: pedido de mais tempo"),
    "camera_pediu_tempo": ("camera", "A câmera viu quem precisa de mais tempo"),
    "travessia_estendida": ("pedestre", "Verde do pedestre estendido"),
    "pedido_recusado_ambulancia": ("ambulancia", "Pedido adiado: ambulância chegando"),
    "pedido_atendido_apos_ambulancia": ("ok", "Pedido atendido depois da ambulância"),
    "modo_alterado": ("rota", "Modo mudou para {modo}"),
    "sem_central_volta_normal": ("alerta", "Sem contato com a central: voltou ao normal"),
    "comando_invalido": ("alerta", "Comando inválido recusado"),
}
_MODOS = {"normal": "Normal", "pedestre": "Pedestre", "escola": "Escola", "chuva": "Chuva", "ambulancia": "Ambulância"}


def _hora(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M:%S")
    except (TypeError, ValueError):
        return "sem horário"


def texto_evento(e: dict) -> tuple[str, str]:
    """Ícone e frase de um sinal do nó, como aparece no feed."""
    ic, txt = _EVENTOS_NO.get(e.get("tipo"), ("duvida", e.get("tipo", "?")))
    modo = (e.get("detalhe") or {}).get("modo")
    return ic, txt.format(modo=_MODOS.get(modo, modo or "?"))


def linha_sinal(e: dict, validacao: dict | None, nome_validador: str = "") -> str:
    """Um sinal do nó com o estado da validação (quem, área e hora) ou 'aguardando'."""
    ic, txt = texto_evento(e)
    cor = AMBAR if ic == "alerta" else VERDE
    simulado = ' <span class="bw-sim">simulado</span>' if (e.get("detalhe") or {}).get("simulado") else ""
    if validacao is None:
        estado = '<span class="bw-val pendente">Aguardando validação do Trânsito ou da Saúde</span>'
    else:
        ok = validacao["decisao"] == "confirmado"
        quem = f'{esc(nome_validador or validacao["usuario"])} · {esc(validacao["area"])} · {_hora(validacao["timestamp"])}'
        motivo = f' · “{esc(validacao["nota"])}”' if validacao.get("nota") else ""
        estado = (f'<span class="bw-val {"ok" if ok else "contestado"}">{"Confirmado" if ok else "Contestado"} por '
                  f'{quem}{motivo}</span>')
    return (f'<div class="bw-sinal">{icone(ic, cor, 20)}<div><b>{esc(txt)}</b>{simulado}<br>{estado}</div>'
            f'<time>{_hora(e.get("recebido_em"))}</time></div>')


def feed_eventos(eventos: list[dict], limite: int = 12) -> str:
    if not eventos:
        return '<div class="bw-feed vazio">Nenhum evento do nó ainda. Eles aparecem aqui assim que o nó relatar algo.</div>'
    itens = []
    for e in eventos[:limite]:
        ic, txt = _EVENTOS_NO.get(e.get("tipo"), ("duvida", e.get("tipo", "?")))
        modo = (e.get("detalhe") or {}).get("modo")
        txt = txt.format(modo=_MODOS.get(modo, modo or "?"))
        cor = AMBAR if ic == "alerta" else VERDE
        selo = ' <span class="bw-sim">simulado</span>' if (e.get("detalhe") or {}).get("simulado") else ""
        itens.append(f'<li>{icone(ic, cor, 20)}<span>{esc(txt)}{selo}</span><time>{_hora(e.get("recebido_em"))}</time></li>')
    return '<ul class="bw-feed">' + "".join(itens) + "</ul>"


# ---------------------------------------------------------------- quadro de ocorrências
_ETAPAS = [("pendente", "Aguardando o Trânsito", "alerta"), ("confirmada", "Aguardando a Saúde", "alerta"),
           ("despachada", "Atendimento a caminho", "ambulancia"), ("concluida", "Concluídas", "ok")]


def _dur(s: float | None) -> str:
    if s is None:
        return "a fazer"
    return f"{s:.0f} s" if s < 120 else f"{s / 60:.0f} min"


def quadro_ocorrencias(linhas: list[dict]) -> str:
    """Colunas por etapa; cada cartão mostra quanto tempo cada etapa levou."""
    colunas = []
    for chave, titulo, ic in _ETAPAS:
        doc = [o for o in linhas if (o["estado"] in ("encerrada", "descartada") if chave == "concluida"
                                     else o["estado"] == chave)]
        cartoes = []
        for o in doc:
            origem = "aberta pela câmera" if o["origem"] == "visao" else "reportada por operador(a)"
            if o["estado"] == "descartada":
                rodape = f'<span class="tag">Descartada</span> {esc(o.get("motivo") or "")}'
            else:
                passos = [("Confirmar", o.get("confirmar")), ("Despachar", o.get("despachar")),
                          ("Atender", o.get("atender"))]
                rodape = "".join(f'<span class="passo{" feito" if v is not None else ""}">{n}<b>{_dur(v)}</b></span>'
                                 for n, v in passos)
            cartoes.append(f'<div class="bw-oc"><div class="t">Nº {o["id"]} · {esc(o["tipo"])}</div>'
                           f'<div class="m">{esc(o["aberta"])} · {origem}</div><div class="p">{rodape}</div></div>')
        corpo = "".join(cartoes) or '<div class="bw-oc vazio">Nenhuma</div>'
        colunas.append(f'<section class="bw-col"><h4>{icone(ic, VERDE if chave == "concluida" else AMBAR, 18)}'
                       f'{titulo}<span class="n">{len(doc)}</span></h4>{corpo}</section>')
    return '<div class="bw-quadro">' + "".join(colunas) + "</div>"


# ---------------------------------------------------------------- ranking, acessos, clipes
def _mortes(n: int | None) -> str:
    if not n:
        return ""
    return f"{n} {'morte' if n == 1 else 'mortes'}"


def ranking_pontos(pontos: list[dict]) -> str:
    topo = max((p["atropelamentos"] for p in pontos), default=1) or 1
    linhas = []
    for p in pontos:
        destaque = " piloto" if p.get("piloto") else ""
        linhas.append(f'<li class="{destaque.strip()}"><span class="r">{p["rank_urbano"]}º</span>'
                      f'<span class="v">{esc(p["via"])}{" · piloto" if p.get("piloto") else ""}</span>'
                      f'<span class="b"><i style="width:{p["atropelamentos"] / topo * 100:.0f}%"></i></span>'
                      f'<b>{p["atropelamentos"]}<small class="m">{_mortes(p.get("mortes"))}</small></b></li>')
    return '<ol class="bw-ranking">' + "".join(linhas) + "</ol>"


def lista_acessos(acessos: list[dict]) -> str:
    if not acessos:
        return '<p class="bw-nota">Ninguém abriu uma câmera ainda.</p>'
    itens = "".join(f'<li><span class="av">{esc(a["usuario"][:1].upper())}</span><b>{esc(a["usuario"])}</b>'
                    f'<span>{esc(a["camera"])}</span><time>{esc(a["quando"])}</time></li>' for a in acessos)
    return f'<ul class="bw-acessos">{itens}</ul>'


_AUX = {"wheelchair": "cadeira de rodas", "walker": "andador", "crutch": "muleta", "cane": "bengala",
        "nenhum": "nenhum auxílio"}


def _aux(v: str) -> str:
    return ", ".join(_AUX.get(x.strip(), x.strip()) for x in str(v).split(","))


def cartoes_clipes(linhas: list[dict]) -> str:
    cartoes = []
    for c in linhas:
        ok = bool(c["acerto"])
        selo = (f'<span class="bw-selo ok">{icone("ok", "currentColor", 15)}Acertou</span>' if ok else
                f'<span class="bw-selo risco">{icone("alerta", "currentColor", 15)}Errou</span>')
        cartoes.append(f'<div class="bw-card bw-clipe">{selo}<h3>{esc(c["clipe"].replace("_", " "))}</h3>'
                       f'<p>Esperado: <b>{_aux(c["auxilio_esperado"])}</b><br>Encontrado: <b>{_aux(c["auxilio_obtido"])}'
                       f'</b></p></div>')
    return '<div class="bw-grid">' + "".join(cartoes) + "</div>"


CSS = f"""
<style>
.bw-semaforo {{ display: flex; gap: 32px; align-items: center; flex-wrap: wrap; }}
.bw-semaforo svg {{ width: 250px; max-width: 100%; height: auto; flex: none; }}
.bw-semaforo .rot {{ fill: var(--bw-muted); font: 500 14px Montserrat, sans-serif; }}
.bw-semaforo .aceso {{ transition: opacity 300ms cubic-bezier(0.22, 1, 0.36, 1); }}
.bw-semaforo circle.aceso {{ filter: drop-shadow(0 0 10px currentColor); }}
.bw-semaforo .leg {{ display: flex; flex-direction: column; gap: 4px; max-width: 32ch; }}
.bw-semaforo .leg b {{ font-size: 20px; line-height: 28px; font-weight: 600; color: var(--bw-texto); }}
.bw-semaforo .leg span {{ color: var(--bw-texto-2); font-size: 16px; line-height: 24px; }}
.bw-semaforo .pisca {{ animation: bwpisca 1s steps(1) infinite; }}
@keyframes bwpisca {{ 50% {{ opacity: .16 !important; }} }}
/* ciclo local (sem o nó): 20 s; carros verde, amarelo, vermelho; pedestre verde no vermelho deles */
.bw-semaforo.local .l-vd {{ animation: lvd 20s steps(1) infinite; }}
.bw-semaforo.local .l-am {{ animation: lam 20s steps(1) infinite; }}
.bw-semaforo.local .l-vm {{ animation: lvm 20s steps(1) infinite; }}
.bw-semaforo.local .p-vd {{ animation: pvd 20s steps(1) infinite; }}
.bw-semaforo.local .p-vm {{ animation: pvm 20s steps(1) infinite; }}
@keyframes lvd {{ 0% {{ opacity: 1; }} 45% {{ opacity: 0; }} }}
@keyframes lam {{ 0% {{ opacity: 0; }} 45% {{ opacity: 1; }} 55% {{ opacity: 0; }} }}
@keyframes lvm {{ 0% {{ opacity: 0; }} 55% {{ opacity: 1; }} }}
@keyframes pvd {{ 0% {{ opacity: .16; }} 60% {{ opacity: 1; }} 85% {{ opacity: .16; }} }}
@keyframes pvm {{ 0% {{ opacity: 1; }} 60% {{ opacity: .16; }} 85% {{ opacity: 1; }} 87% {{ opacity: .16; }}
  89% {{ opacity: 1; }} 91% {{ opacity: .16; }} 93% {{ opacity: 1; }} }}
@media (prefers-reduced-motion: reduce) {{ .bw-semaforo .pisca, .bw-semaforo.local .aceso {{ animation: none; }} }}
.bw-feed {{ list-style: none; margin: 0; padding: 0; background: {CARTAO}; border: 1px solid var(--bw-borda); border-radius: 16px; }}
.bw-feed li {{ display: grid; grid-template-columns: 26px 1fr auto; gap: 10px; align-items: center;
  padding: 12px 16px; border-top: 1px solid var(--bw-borda); font-size: 15px; }}
.bw-feed li:first-child {{ border-top: 0; }}
.bw-sinal {{ display: grid; grid-template-columns: 26px 1fr auto; gap: 10px; align-items: start; padding: 12px 14px 12px;
  font-size: 14px; line-height: 1.45; }}
.bw-sinal time {{ color: {MUTED}; font-variant-numeric: tabular-nums; }}
.bw-sim {{ background: var(--bw-borda); color: var(--bw-texto-2); border-radius: 999px; padding: 1px 8px; font-size: 12px; font-weight: 600; }}
.bw-val {{ font-size: 13px; }}
.bw-val.pendente {{ color: var(--bw-ambar-texto); }}
.bw-val.ok {{ color: var(--bw-destaque); }}
.bw-val.contestado {{ color: var(--bw-alerta-texto); }}
[class*="st-key-sinal_"] {{ background: {CARTAO}; border: 1px solid var(--bw-borda); border-radius: 14px; padding: 0 0 10px; gap: 4px; }}
[class*="st-key-sinal_"] [data-testid="stHorizontalBlock"] {{ padding: 0 14px 0 50px; }}
.bw-feed time {{ color: {MUTED}; font-variant-numeric: tabular-nums; font-size: 14px; }}
.bw-feed.vazio {{ padding: 16px; color: {MUTED}; font-size: 15px; }}
.bw-quadro {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }}
.bw-col {{ background: var(--bw-cartao-2); border-radius: 16px; padding: 12px; min-height: 140px; }}
.bw-col h4 {{ display: flex; align-items: center; gap: 8px; margin: 4px 4px 12px; font-size: 16px; font-weight: 600; }}
.bw-col h4 .n {{ margin-left: auto; background: var(--bw-borda); border-radius: 999px; padding: 1px 10px; font-size: 14px; }}
.bw-oc {{ background: {CARTAO}; border: 1px solid var(--bw-borda); border-radius: 12px; padding: 12px 14px; margin-bottom: 10px; }}
.bw-oc .t {{ font-weight: 600; font-size: 15px; }}
.bw-oc .m {{ color: {MUTED}; font-size: 14px; margin: 2px 0 10px; }}
.bw-oc .p {{ display: flex; gap: 6px; flex-wrap: wrap; font-size: 14px; color: var(--bw-texto-2); }}
.bw-oc .passo {{ background: var(--bw-borda); border-radius: 8px; padding: 4px 8px; display: flex; gap: 6px; }}
.bw-oc .passo.feito {{ background: rgba(0,194,122,.16); }}
.bw-oc .passo b {{ color: {VERDE}; }}
.bw-oc .tag {{ background: var(--bw-borda); border-radius: 8px; padding: 4px 8px; }}
.bw-oc.vazio {{ color: {MUTED}; font-size: 14px; text-align: center; }}
.bw-ranking {{ list-style: none; margin: 0; padding: 0; }}
.bw-ranking li {{ display: grid; grid-template-columns: 40px minmax(0, 1.3fr) 1fr 74px; gap: 10px; align-items: center;
  padding: 7px 0; font-size: 15px; border-top: 1px solid var(--bw-borda); }}
.bw-ranking li .r {{ color: {MUTED}; font-variant-numeric: tabular-nums; }}
.bw-ranking li .v {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.bw-ranking li .b {{ background: var(--bw-borda); border-radius: 6px; height: 10px; overflow: hidden; }}
.bw-ranking li .b i {{ display: block; height: 100%; background: {ALERTA}; border-radius: 6px; }}
.bw-ranking li b {{ text-align: right; }}
.bw-ranking li b .m {{ display: block; color: {MUTED}; font-weight: 500; font-size: 12px; }}
.bw-ranking li.piloto .v {{ color: {VERDE}; font-weight: 600; }}
.bw-ranking li.piloto .b i {{ background: {VERDE}; }}
.bw-acessos {{ list-style: none; margin: 0; padding: 0; }}
.bw-acessos li {{ display: grid; grid-template-columns: 34px auto 1fr auto; gap: 10px; align-items: center; padding: 8px 0;
  border-top: 1px solid var(--bw-borda); font-size: 15px; }}
.bw-acessos .av {{ width: 30px; height: 30px; border-radius: 50%; background: var(--bw-borda); display: grid; place-items: center;
  font-weight: 700; color: {VERDE}; }}
.bw-acessos time {{ color: {MUTED}; font-size: 14px; }}
.bw-clipe h3 {{ text-transform: capitalize; }}
</style>
"""
_ = ALERTA_INK
