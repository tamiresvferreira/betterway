"""Animação do Estudo A, lado a lado (sem × com a BetterWay), desenhada a partir da simulação do SUMO.

    python src/simulacao/animacao_estudo_a.py      # gera GIF e MP4 em docs/evidencias/estudo_a/

Cada cena roda a MESMA simulação e as MESMAS regras do estudo (src/simulacao/estudo_a.py), com uma demanda curta
e fixa para a história ficar clara; a posição de cada carro e de cada pessoa é lida a cada 0,2 s. Ninguém real aparece:
pessoas são pontos, carros são retângulos. Resultados ESPERADOS de simulação (regra 8). Cores e fonte: kit BetterWay.
"""
from __future__ import annotations

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Polygon, Rectangle, Circle, FancyBboxPatch  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estudo_a as ea  # noqa: E402

traci = ea.traci
RAIZ = ea.RAIZ
FONTES = RAIZ / "assets" / "marca" / "fontes"
for _f in sorted(FONTES.glob("Montserrat-*.ttf")):
    font_manager.fontManager.addfont(str(_f))
if any(FONTES.glob("Montserrat-*.ttf")):
    plt.rcParams["font.family"] = "Montserrat"

# kit BetterWay (tokens.json)
GRAFITE, FUNDO, VERDE, VERDE_ESC = "#1a1d21", "#f4f4ef", "#00c27a", "#006b44"
AMBAR, ALERTA, CARTAO, MUTED = "#ffb000", "#e63946", "#2a2e33", "#9aa1aa"
ASFALTO, CALCADA = "#33383e", "#4a5058"
PASSO = 0.2
JANELA_M = 30


# ---------------------------------------------------------------- cenas (demanda curta e fixa)
def _demanda_cena(cena: str, inicio_pessoas: list[tuple[float, str, str, str]], ambulancia_em: float | None):
    def gerar(pasta: Path) -> Path:
        r = ET.Element("routes")
        ET.SubElement(r, "vType", id="carro", vClass="passenger", emissionClass="HBEFA4/PC_petrol_Euro-4")
        ET.SubElement(r, "vType", id="ambulancia", vClass="emergency", speedFactor="1.3",
                      emissionClass="HBEFA4/PC_diesel_Euro-4")
        for tipo, v in (("pedestre", ea.VEL_NORMAL), ("pedestre_reduzida", ea.VEL_REDUZIDA)):
            ET.SubElement(r, "vType", id=tipo, vClass="pedestrian", desiredMaxSpeed=str(v), maxSpeed=str(v),
                          speedDev="0")
        for i, (a, b, vph) in enumerate(ea.FLUXOS):
            ET.SubElement(r, "flow", id=f"f{i}", type="carro", begin="0", end="400", vehsPerHour=str(vph),
                          **{"from": f"{a}C", "to": f"C{b}", "departLane": "best", "departSpeed": "max"})
        eventos = [(t, "p", (pid, tipo, de)) for t, pid, tipo, de in inicio_pessoas]
        if ambulancia_em is not None:
            eventos.append((ambulancia_em, "a", None))
        for t, k, dado in sorted(eventos, key=lambda e: e[0]):
            if k == "a":
                ET.SubElement(r, "trip", id="amb0", type="ambulancia", depart=f"{t:.1f}",
                              **{"from": "OC", "to": "CL", "departLane": "best"})
            else:
                pid, tipo, de = dado
                para = "CS" if de == "NC" else "CN"
                p = ET.SubElement(r, "person", id=pid, type=tipo, depart=f"{t:.1f}", departPos=str(ea.BRACO_M - 15))
                ET.SubElement(p, "walk", arrivalPos="15", **{"from": de, "to": para})
        arq = pasta / "cena.rou.xml"
        ET.ElementTree(r).write(arq, encoding="utf-8")
        return arq
    return gerar


CENAS = {
    # a pessoa com mobilidade reduzida chega à faixa no vermelho e começa a atravessar no início do verde (19 s):
    # precisa de 20 s para os 16 m — sem o sistema, o verde dos carros abre com ela no meio da faixa
    "pedestre": dict(comparacao="pedestre", janela=(112, 168),
                     pessoas=[(95, "lenta", "pedestre_reduzida", "NC"), (101, "p1", "pedestre", "SC"),
                              (104, "p2", "pedestre", "NC")], ambulancia=None,
                     titulo="Travessia de uma pessoa com mobilidade reduzida (0,8 m/s, faixa de 16 m, verde de 19 s)"),
    # a ambulância chega com o vermelho da avenida e uma pessoa atravessando: com o sistema, o verde abre para ela
    # assim que a faixa esvazia — nunca com alguém no meio
    "ambulancia": dict(comparacao="ambulancia", janela=(36, 92),
                       pessoas=[(27, "p1", "pedestre", "NC"), (33, "p2", "pedestre", "SC")], ambulancia=41.0,
                       titulo="Ambulância chegando com o semáforo fechado para ela e uma pessoa na faixa"),
}


def capturar(cena: str, com_sistema: bool) -> list[dict]:
    c = CENAS[cena]
    quadros = []
    ini, fim = c["janela"]

    def ao_passo(estado):
        t = traci.simulation.getTime()
        if t < ini or t > fim:
            return
        trav = ea._travessias()
        faixas = {f for _, f in trav}
        q = {"t": t, "verde_ped": any(estado[i] in "Gg" for i, _ in trav),
             "verde_avenida": any(estado[i] in "Gg" for i, l in enumerate(traci.trafficlight.getControlledLinks(ea.TLS))
                                  if l and l[0][0].startswith("OC_")),
             "carros": [], "pessoas": []}
        for v in traci.vehicle.getIDList():
            x, y = traci.vehicle.getPosition(v)
            q["carros"].append((x, y, traci.vehicle.getAngle(v), traci.vehicle.getTypeID(v),
                                traci.vehicle.getLength(v), traci.vehicle.getSpeed(v)))
        for p in traci.person.getIDList():
            x, y = traci.person.getPosition(p)
            q["pessoas"].append((x, y, traci.person.getTypeID(p), traci.person.getLaneID(p) in faixas))
        quadros.append(q)

    ea.rodar(c["comparacao"], com_sistema, 1, duracao=int(fim) + 30,
             demanda=_demanda_cena(cena, c["pessoas"], c["ambulancia"]), ao_passo=ao_passo, passo_s=PASSO)
    return quadros


# ---------------------------------------------------------------- desenho
def _geometria():
    import sumolib
    net = sumolib.net.readNet(str(ea.gerar_rede("static")), withInternal=True, withPedestrianConnections=True)
    cx, cy = net.getNode("C").getCoord()
    pistas, calcadas, faixas, juncoes = [], [], [], []
    for e in net.getEdges(withInternal=True):
        for ln in e.getLanes():
            forma = ln.getShape()
            if len(forma) < 2:
                continue
            w = ln.getWidth()
            if e.getFunction() == "crossing":
                faixas.append((forma, w))
            elif e.getFunction() == "walkingarea":
                continue
            elif ln.allows("pedestrian") and not ln.allows("passenger"):
                calcadas.append((forma, w))
            elif e.getFunction() == "":
                pistas.append((forma, w))
    for n in net.getNodes():
        if n.getShape():
            juncoes.append(n.getShape())
    return (cx, cy), pistas, calcadas, faixas, juncoes


def _faixa_poligono(forma, w):
    pts = np.array(forma, float)
    esq, dir_ = [], []
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        d = b - a
        n = np.array([-d[1], d[0]]) / (np.hypot(*d) or 1)
        esq.append(p + n * w / 2)
        dir_.append(p - n * w / 2)
    return np.vstack([esq, dir_[::-1]])


def _desenhar_painel(ax, geo, q, com_sistema, cena, inicio_verde):
    (cx, cy), pistas, calcadas, faixas, juncoes = geo
    ax.set_facecolor(GRAFITE)
    ax.set_xlim(cx - JANELA_M, cx + JANELA_M)
    ax.set_ylim(cy - JANELA_M, cy + JANELA_M)
    ax.set_aspect("equal")
    ax.axis("off")
    for forma, w in calcadas:
        ax.add_patch(Polygon(_faixa_poligono(forma, w), closed=True, color=CALCADA, lw=0))
    for forma in juncoes:
        ax.add_patch(Polygon(np.array(forma), closed=True, color=ASFALTO, lw=0))
    for forma, w in pistas:
        ax.add_patch(Polygon(_faixa_poligono(forma, w), closed=True, color=ASFALTO, lw=0))
    # faixas de pedestre: zebra, com a cor do sinal do pedestre na borda
    borda = VERDE if q["verde_ped"] else ALERTA
    for forma, w in faixas:
        poly = _faixa_poligono(forma, w)
        a0, b0 = np.array(forma[0], float), np.array(forma[-1], float)
        if np.hypot(*(b0 - a0)) > 10:          # só as faixas da avenida (as que o estudo mede) levam a cor do sinal
            ax.add_patch(Polygon(poly, closed=True, facecolor="none", edgecolor=borda, lw=2.2, alpha=0.95))
        a, b = np.array(forma[0], float), np.array(forma[-1], float)
        comp = np.hypot(*(b - a))
        n_listras = int(comp // 1.0)
        for k in range(n_listras):
            if k % 2:
                continue
            p0 = a + (b - a) * (k / n_listras)
            p1 = a + (b - a) * ((k + 1) / n_listras)
            ax.add_patch(Polygon(_faixa_poligono([tuple(p0), tuple(p1)], w * 0.86), closed=True, color=FUNDO,
                                 alpha=0.28, lw=0))
    # veículos (retângulo na direção do movimento; a posição do SUMO é o para-choque dianteiro)
    for x, y, ang, tipo, comp, vel in q["carros"]:
        rad = math.radians(90 - ang)
        dx, dy = math.cos(rad), math.sin(rad)
        corpo_x, corpo_y = x - dx * comp / 2, y - dy * comp / 2
        cor = ALERTA if tipo == "ambulancia" else MUTED
        r = Rectangle((corpo_x - comp / 2, corpo_y - 0.9), comp, 1.8, angle=0, color=cor, lw=0)
        t = matplotlib.transforms.Affine2D().rotate_deg_around(corpo_x, corpo_y, 90 - ang) + ax.transData
        r.set_transform(t)
        ax.add_patch(r)
        if tipo == "ambulancia":
            ax.text(corpo_x, corpo_y + 3.0, "Ambulância", color=FUNDO, fontsize=9, ha="center", fontweight="bold")
    # pessoas
    for x, y, tipo, na_faixa in q["pessoas"]:
        lenta = tipo == "pedestre_reduzida"
        ax.add_patch(Circle((x, y), 1.25 if lenta else 0.8, color=AMBAR if lenta else FUNDO, lw=0, zorder=5))
        if lenta:
            ax.text(x - 3.0, y, "mobilidade reduzida", color=AMBAR, fontsize=9.5, va="center", ha="right", zorder=6,
                    fontweight="bold", bbox=dict(boxstyle="round,pad=0.25", facecolor=GRAFITE, edgecolor="none",
                                                 alpha=0.85))
    # placa de estado (sinal do pedestre e da avenida)
    t_verde = q["t"] - inicio_verde if (q["verde_ped"] and inicio_verde is not None) else None
    txt_ped = f"Pedestre: VERDE ({t_verde:.0f} s)" if t_verde is not None else "Pedestre: VERMELHO"
    ax.text(cx - JANELA_M + 2, cy + JANELA_M - 4, txt_ped, color=VERDE if q["verde_ped"] else ALERTA,
            fontsize=10, fontweight="bold")
    ax.text(cx - JANELA_M + 2, cy + JANELA_M - 8, "Avenida: " + ("VERDE" if q["verde_avenida"] else "VERMELHO"),
            color=VERDE if q["verde_avenida"] else ALERTA, fontsize=10, fontweight="bold")


def _aviso(q, com_sistema, cena, inicio_verde):
    lenta_na_faixa = any(t == "pedestre_reduzida" and f for _, _, t, f in q["pessoas"])
    alguem_na_faixa = any(f for *_, f in q["pessoas"])
    amb = [c for c in q["carros"] if c[3] == "ambulancia"]
    if cena == "pedestre":
        if lenta_na_faixa and not q["verde_ped"]:
            return "O sinal do pedestre fechou com ela no meio da faixa", ALERTA
        if lenta_na_faixa and q["verde_ped"] and inicio_verde is not None and q["t"] - inicio_verde > ea.VERDE_PEDESTRE_S:
            return "Verde do pedestre estendido até ela terminar", VERDE
        if lenta_na_faixa:
            return "Atravessando: precisa de 20 s, o verde tem 19 s", AMBAR
        return None, None
    if amb:
        x, y, ang, tipo, comp, vel = amb[0]
        if vel < 1 and alguem_na_faixa:
            return ("Ambulância espera a faixa esvaziar" if com_sistema else "Ambulância parada no vermelho"), AMBAR
        if vel < 1:
            return "Ambulância parada no vermelho", ALERTA
        if com_sistema and q["verde_avenida"]:
            return "Verde aberto para a ambulância (faixa vazia)", VERDE
    return None, None


def renderizar(cena: str, saida_gif: Path, saida_mp4: Path | None = None, de_quadro: int = 2) -> dict:
    import cv2
    from PIL import Image
    geo = _geometria()
    sem, com = capturar(cena, False), capturar(cena, True)
    n = min(len(sem), len(com))
    quadros_gif, escritor = [], None
    estado = {"sem": None, "com": None}
    resumo = {"quadros": n}
    for i in range(0, n, 1):
        fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor=GRAFITE)
        fig.text(0.03, 0.93, "BetterWay", color=FUNDO, fontsize=20, fontweight="bold")
        fig.text(0.165, 0.93, "·  Estudo A no SUMO", color=VERDE, fontsize=20, fontweight="bold")
        fig.text(0.03, 0.892, CENAS[cena]["titulo"], color=MUTED, fontsize=11)
        for k, (nome, frames, com_sis, x0) in enumerate((("Sem a BetterWay", sem, False, 0.03),
                                                         ("Com a BetterWay", com, True, 0.52))):
            q = frames[i]
            chave = "com" if com_sis else "sem"
            if q["verde_ped"] and estado[chave] is None:
                estado[chave] = q["t"]
            if not q["verde_ped"]:
                estado[chave] = None
            ax = fig.add_axes([x0, 0.1, 0.45, 0.74])
            _desenhar_painel(ax, geo, q, com_sis, cena, estado[chave])
            fig.text(x0, 0.845, nome, color=VERDE if com_sis else FUNDO, fontsize=14, fontweight="bold")
            aviso, cor = _aviso(q, com_sis, cena, estado[chave])
            if aviso:
                fig.add_artist(FancyBboxPatch((x0, 0.035), 0.45, 0.05, boxstyle="round,pad=0.004,rounding_size=0.012",
                                              transform=fig.transFigure, facecolor=cor, edgecolor="none"))
                fig.text(x0 + 0.225, 0.06, aviso, color=GRAFITE, fontsize=11.5, fontweight="bold", ha="center",
                         va="center")
        fig.text(0.97, 0.93, f"t = {sem[i]['t'] - sem[0]['t']:4.1f} s", color=MUTED, fontsize=11, ha="right")
        fig.text(0.97, 0.895, "resultado ESPERADO de simulação", color=MUTED, fontsize=9, ha="right")
        fig.canvas.draw()
        img = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
        plt.close(fig)
        if saida_mp4 is not None:
            if escritor is None:
                escritor = cv2.VideoWriter(str(saida_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 1 / PASSO / 2,
                                           (img.shape[1], img.shape[0]))
            escritor.write(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        if i % de_quadro == 0:
            quadros_gif.append(Image.fromarray(img).resize((960, 540)))
    if escritor is not None:
        escritor.release()
    quadros_gif[0].save(saida_gif, save_all=True, append_images=quadros_gif[1:],
                        duration=int(1000 * PASSO * de_quadro / 2.5), loop=0, optimize=True)
    resumo["lenta_surpreendida_sem"] = any(not q["verde_ped"] and any(t == "pedestre_reduzida" and f for _, _, t, f in q["pessoas"]) for q in sem)
    resumo["lenta_surpreendida_com"] = any(not q["verde_ped"] and any(t == "pedestre_reduzida" and f for _, _, t, f in q["pessoas"]) for q in com)
    return resumo


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ea.EVID.mkdir(parents=True, exist_ok=True)
    for cena in CENAS:
        r = renderizar(cena, ea.EVID / f"animacao_{cena}.gif", ea.EVID / f"animacao_{cena}.mp4")
        print(cena, r)


if __name__ == "__main__":
    main()
