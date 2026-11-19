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


def semaforo_svg(fase: str | None) -> str:
    """Dois grupos focais desenhados: o dos carros (3 luzes) e o do pedestre (2 luzes), com o estado escrito."""
    carros, ped = _FASES.get(fase or "", (None, None))

    def luz(cx, cy, cor_nome, acesa, extra=""):
        cor = _COR_LUZ[cor_nome]
        return (f'<circle cx="{cx}" cy="{cy}" r="15" fill="{cor if acesa else "#3A4047"}" '
                f'opacity="{1 if acesa else .55}" {extra}/>')
    pisca = 'class="pisca"' if ped == "pisca" else ""
    svg = (f'<svg viewBox="0 0 200 150" width="200" height="150" role="img" '
           f'aria-label="Semáforo: carros {carros or "sem sinal"}, pedestre {ped or "sem sinal"}" '
           f'data-carros="{carros or "nenhum"}" data-pedestre="{"vermelho" if ped == "pisca" else ped or "nenhum"}">'
           f'<rect x="20" y="5" width="50" height="135" rx="14" fill="#111417" stroke="#3A4047"/>'
           + luz(45, 32, "vermelho", carros == "vermelho") + luz(45, 72, "amarelo", carros == "amarelo")
           + luz(45, 112, "verde", carros == "verde") +
           f'<rect x="120" y="35" width="50" height="95" rx="14" fill="#111417" stroke="#3A4047"/>'
           + luz(145, 62, "vermelho", ped in ("vermelho", "pisca"), pisca) + luz(145, 102, "verde", ped == "verde")
           + '</svg>')
    if carros is None:
        legenda = "<b>Sem sinal do nó</b><span>o nó ainda não respondeu</span>"
    else:
        legenda = (f"<b>Carros: {carros}</b><span>Pedestre: "
                   f"{'vermelho piscando (termine a travessia)' if ped == 'pisca' else ped}</span>")
    return f'<div class="bw-semaforo">{svg}<div class="leg">{legenda}</div></div>'


# ---------------------------------------------------------------- feed de eventos do nó
_EVENTOS_NO = {
    "botao_pressionado": ("pedestre", "Botão de travessia apertado"),
    "travessia_estendida": ("pedestre", "Verde do pedestre estendido"),
    "botao_recusado_ambulancia": ("ambulancia", "Botão recusado: ambulância chegando"),
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
        itens.append(f'<li>{icone(ic, cor, 20)}<span>{esc(txt)}</span><time>{_hora(e.get("recebido_em"))}</time></li>')
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
.bw-semaforo {{ display: flex; gap: 22px; align-items: center; background: {CARTAO}; border: 1px solid #343A41;
  border-radius: 16px; padding: 16px 20px; flex-wrap: wrap; }}
.bw-semaforo .leg {{ display: flex; flex-direction: column; gap: 4px; font-size: 18px; }}
.bw-semaforo .leg span {{ color: #C9CBC6; font-size: 15px; }}
.bw-semaforo .pisca {{ animation: bwpisca 1s steps(1) infinite; }}
@keyframes bwpisca {{ 50% {{ opacity: .2; }} }}
@media (prefers-reduced-motion: reduce) {{ .bw-semaforo .pisca {{ animation: none; }} }}
.bw-feed {{ list-style: none; margin: 0; padding: 0; background: {CARTAO}; border: 1px solid #343A41; border-radius: 16px; }}
.bw-feed li {{ display: grid; grid-template-columns: 26px 1fr auto; gap: 10px; align-items: center;
  padding: 12px 16px; border-top: 1px solid #343A41; font-size: 15px; }}
.bw-feed li:first-child {{ border-top: 0; }}
.bw-sinal {{ display: grid; grid-template-columns: 26px 1fr auto; gap: 10px; align-items: start; padding: 12px 14px 12px;
  font-size: 14px; line-height: 1.45; }}
.bw-sinal time {{ color: {MUTED}; font-variant-numeric: tabular-nums; }}
.bw-sim {{ background: #343A41; color: #C9CBC6; border-radius: 999px; padding: 1px 8px; font-size: 12px; font-weight: 600; }}
.bw-val {{ font-size: 13px; }}
.bw-val.pendente {{ color: {AMBAR}; }}
.bw-val.ok {{ color: {VERDE}; }}
.bw-val.contestado {{ color: #FF8A92; }}
[class*="st-key-sinal_"] {{ background: {CARTAO}; border: 1px solid #343A41; border-radius: 14px; padding: 0 0 10px; gap: 4px; }}
[class*="st-key-sinal_"] [data-testid="stHorizontalBlock"] {{ padding: 0 14px 0 50px; }}
.bw-feed time {{ color: {MUTED}; font-variant-numeric: tabular-nums; font-size: 14px; }}
.bw-feed.vazio {{ padding: 16px; color: {MUTED}; font-size: 15px; }}
.bw-quadro {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }}
.bw-col {{ background: #23272C; border-radius: 16px; padding: 12px; min-height: 140px; }}
.bw-col h4 {{ display: flex; align-items: center; gap: 8px; margin: 4px 4px 12px; font-size: 16px; font-weight: 600; }}
.bw-col h4 .n {{ margin-left: auto; background: #343A41; border-radius: 999px; padding: 1px 10px; font-size: 14px; }}
.bw-oc {{ background: {CARTAO}; border: 1px solid #343A41; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px; }}
.bw-oc .t {{ font-weight: 600; font-size: 15px; }}
.bw-oc .m {{ color: {MUTED}; font-size: 14px; margin: 2px 0 10px; }}
.bw-oc .p {{ display: flex; gap: 6px; flex-wrap: wrap; font-size: 14px; color: #C9CBC6; }}
.bw-oc .passo {{ background: #343A41; border-radius: 8px; padding: 4px 8px; display: flex; gap: 6px; }}
.bw-oc .passo.feito {{ background: rgba(0,194,122,.16); }}
.bw-oc .passo b {{ color: {VERDE}; }}
.bw-oc .tag {{ background: #343A41; border-radius: 8px; padding: 4px 8px; }}
.bw-oc.vazio {{ color: {MUTED}; font-size: 14px; text-align: center; }}
.bw-ranking {{ list-style: none; margin: 0; padding: 0; }}
.bw-ranking li {{ display: grid; grid-template-columns: 40px minmax(0, 1.3fr) 1fr 74px; gap: 10px; align-items: center;
  padding: 7px 0; font-size: 15px; border-top: 1px solid #343A41; }}
.bw-ranking li .r {{ color: {MUTED}; font-variant-numeric: tabular-nums; }}
.bw-ranking li .v {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.bw-ranking li .b {{ background: #343A41; border-radius: 6px; height: 10px; overflow: hidden; }}
.bw-ranking li .b i {{ display: block; height: 100%; background: {ALERTA}; border-radius: 6px; }}
.bw-ranking li b {{ text-align: right; }}
.bw-ranking li b .m {{ display: block; color: {MUTED}; font-weight: 500; font-size: 12px; }}
.bw-ranking li.piloto .v {{ color: {VERDE}; font-weight: 600; }}
.bw-ranking li.piloto .b i {{ background: {VERDE}; }}
.bw-acessos {{ list-style: none; margin: 0; padding: 0; }}
.bw-acessos li {{ display: grid; grid-template-columns: 34px auto 1fr auto; gap: 10px; align-items: center; padding: 8px 0;
  border-top: 1px solid #343A41; font-size: 15px; }}
.bw-acessos .av {{ width: 30px; height: 30px; border-radius: 50%; background: #343A41; display: grid; place-items: center;
  font-weight: 700; color: {VERDE}; }}
.bw-acessos time {{ color: {MUTED}; font-size: 14px; }}
.bw-clipe h3 {{ text-transform: capitalize; }}
</style>
"""
_ = ALERTA_INK
