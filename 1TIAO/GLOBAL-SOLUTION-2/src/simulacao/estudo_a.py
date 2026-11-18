"""Estudo A — simulação no SUMO de um cruzamento semaforizado calibrado pelo do piloto (Largo da Concórdia).

O cruzamento é SINTÉTICO (avenida com 3 faixas por sentido × rua com 1 faixa por sentido, braços de 300 m), com os
números medidos no mapa real do piloto (OpenStreetMap → netconvert, em data/raw/osm/largo_concordia.osm): faixa de
pedestre de ~16 m atravessando a avenida e verde do pedestre de 19 s. O mapa real foi tentado primeiro e descartado:
o recorte tem faixas duplicadas e vias de 0,2 a 3 m nas junções, e os fluxos atravessavam outros semáforos estimados,
engarrafando a rede (ver docs/evidencias/estudo_a/README.md). Trânsito: fluxos ESTIMADOS (não há contagem da CET).
Tudo aqui é "resultado esperado" de simulação (regra 8).

Comparações (cada uma sem × com o sistema, várias sementes):
  1. pedestre    — verde do pedestre fixo × estendido quando há pessoa com mobilidade reduzida (0,8 m/s) na faixa
  2. semaforo    — semáforo de tempo fixo × atuado (adaptativo, por detectores)
  3. ambulancia  — ambulância sem × com prioridade (verde para ela, sem cortar quem está na faixa)
  (alagamento: fora, por tempo — já coberto pela central e pelo nó, como combinado)

    python src/simulacao/estudo_a.py            # roda tudo e grava docs/evidencias/estudo_a/
"""
from __future__ import annotations

import csv
import os
import random
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SUMO_PKG = RAIZ.parents[1] / ".venv" / "Lib" / "site-packages" / "sumo"
os.environ.setdefault("SUMO_HOME", str(SUMO_PKG))
sys.path.append(str(SUMO_PKG / "tools"))
import traci  # noqa: E402

PASTA = Path(__file__).resolve().parent / "rede"
EVID = RAIZ / "docs" / "evidencias" / "estudo_a"
TLS = "C"
VEL_NORMAL, VEL_REDUZIDA = 1.2, 0.8      # m/s — as mesmas velocidades de projeto do nó ESP32
LARGURA_FAIXA_M = 2.7                    # 3 faixas × 2,7 m ≈ 16 m de travessia (a do piloto tem 16 m)
VERDE_PEDESTRE_S = 19                    # o verde da faixa do piloto (programa estimado pelo netconvert)
VERDE_AVENIDA_S = 40
FOLGA_S = 2.0
DURACAO_S = 1800                         # 30 min por rodada
BRACO_M = 300
# fluxos ESTIMADOS (veículos/h): avenida nos dois sentidos, rua transversal nos dois sentidos
FLUXOS = [("O", "L", 900), ("L", "O", 800), ("N", "S", 250), ("S", "N", 200)]
PEDESTRES_H = 160            # pessoas/h atravessando a avenida (as duas direções)
FRACAO_REDUZIDA = 0.15       # parte delas com mobilidade reduzida (estimativa)
# 6 ambulâncias por rodada, espaçadas 67 s (o ciclo tem 75 s): chegam em momentos diferentes do semáforo
AMBULANCIAS = [(f"amb{k}", 300 + 67 * k) for k in range(6)]


def gerar_rede(tipo: str = "static") -> Path:
    """Cruzamento em cruz: avenida O–L (3 faixas por sentido) × rua N–S (1 faixa); calçadas e faixas de pedestre."""
    PASTA.mkdir(exist_ok=True)
    rede = PASTA / f"cruzamento_{tipo}.net.xml"
    if rede.exists():
        return rede
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nos = ET.Element("nodes")
        for nid, x, y, t in [("C", 0, 0, "traffic_light"), ("O", -BRACO_M, 0, "priority"), ("L", BRACO_M, 0, "priority"),
                             ("N", 0, BRACO_M, "priority"), ("S", 0, -BRACO_M, "priority")]:
            ET.SubElement(nos, "node", id=nid, x=str(x), y=str(y), type=t)
        ET.ElementTree(nos).write(tmp / "n.nod.xml")
        arestas = ET.Element("edges")
        for a, b in [("O", "C"), ("C", "L"), ("L", "C"), ("C", "O")]:
            ET.SubElement(arestas, "edge", id=f"{a}{b}", **{"from": a, "to": b}, numLanes="3", speed="13.89",
                          width=str(LARGURA_FAIXA_M))
        for a, b in [("N", "C"), ("C", "S"), ("S", "C"), ("C", "N")]:
            ET.SubElement(arestas, "edge", id=f"{a}{b}", **{"from": a, "to": b}, numLanes="1", speed="11.11")
        ET.ElementTree(arestas).write(tmp / "e.edg.xml")
        subprocess.run([str(SUMO_PKG / "bin" / "netconvert.exe"), "-n", str(tmp / "n.nod.xml"), "-e",
                        str(tmp / "e.edg.xml"), "-o", str(rede), "--sidewalks.guess", "--crossings.guess",
                        "--tls.default-type", tipo, "--no-turnarounds", "--no-warnings"], check=True,
                       capture_output=True)
    return rede


def _travessias() -> list[tuple[int, str]]:
    """(índice do link, faixa) das travessias da avenida (~16 m; as da rua transversal são curtas)."""
    out = []
    for i, l in enumerate(traci.trafficlight.getControlledLinks(TLS)):
        if l and l[0][1].startswith(":C_c") and traci.lane.getLength(l[0][1]) > 10:
            out.append((i, l[0][1]))
    return out


def _programa_fixo():
    """Ajusta o programa estimado: verde da avenida 40 s e verde da faixa de pedestre 19 s (o do piloto)."""
    logic = traci.trafficlight.getAllProgramLogics(TLS)[0]
    idx = [i for i, _ in _travessias()]
    fases = []
    for f in logic.phases:
        dur = f.duration
        # só os verdes principais (as fases longas do programa estimado, 37 s); as transições de 5 s e os amarelos
        # ficam como estão (antes, a regra alongava também as de 5 s e o ciclo ia a 145 s)
        if f.duration > 10:
            dur = VERDE_PEDESTRE_S if any(f.state[i] in "Gg" for i in idx) else VERDE_AVENIDA_S
        fases.append(traci.trafficlight.Phase(dur, f.state, dur, dur))
    traci.trafficlight.setProgramLogic(TLS, traci.trafficlight.Logic(logic.programID, logic.type, 0, fases))


def _demanda(pasta: Path, semente: int, ambulancia: bool, duracao: int) -> Path:
    rng = random.Random(semente)
    r = ET.Element("routes")
    ET.SubElement(r, "vType", id="carro", vClass="passenger", emissionClass="HBEFA4/PC_petrol_Euro-4")
    ET.SubElement(r, "vType", id="ambulancia", vClass="emergency", color="1,0,0", speedFactor="1.3",
                  emissionClass="HBEFA4/PC_diesel_Euro-4")
    for tipo, v in (("pedestre", VEL_NORMAL), ("pedestre_reduzida", VEL_REDUZIDA)):
        ET.SubElement(r, "vType", id=tipo, vClass="pedestrian", desiredMaxSpeed=str(v), maxSpeed=str(v), speedDev="0")
    for i, (a, b, vph) in enumerate(FLUXOS):
        ET.SubElement(r, "flow", id=f"f{i}", type="carro", begin="0", end=str(duracao), vehsPerHour=str(vph),
                      **{"from": f"{a}C", "to": f"C{b}", "departLane": "best", "departSpeed": "max"})
    # pessoas e ambulâncias entram JUNTAS, em ordem de partida: o SUMO descarta, sem aviso com --no-warnings, todo
    # elemento que vem fora de ordem (antes, 32 de 87 pessoas sumiam nas rodadas da ambulância)
    eventos = []
    if ambulancia:
        for aid, dep in AMBULANCIAS:
            eventos.append((float(dep), "amb", aid))
    # pedestres atravessando a avenida: da calçada norte para a sul e vice-versa
    t, n = 0.0, 0
    while True:
        t += rng.expovariate(PEDESTRES_H / 3600)
        if t >= duracao:
            break
        tipo = "pedestre_reduzida" if rng.random() < FRACAO_REDUZIDA else "pedestre"
        de, para = ("NC", "CS") if rng.random() < 0.5 else ("SC", "CN")
        eventos.append((round(t, 1), "pessoa", (f"p{n}", tipo, de, para)))
        n += 1
    for dep, tipo_ev, dado in sorted(eventos, key=lambda e: e[0]):
        if tipo_ev == "amb":
            ET.SubElement(r, "trip", id=dado, type="ambulancia", depart=f"{dep:.1f}",
                          **{"from": "OC", "to": "CL", "departLane": "best"})
        else:
            pid, tipo, de, para = dado
            p = ET.SubElement(r, "person", id=pid, type=tipo, depart=f"{dep:.1f}", departPos=str(BRACO_M - 15))
            ET.SubElement(p, "walk", arrivalPos="15", **{"from": de, "to": para})
    arq = pasta / "demanda.rou.xml"
    ET.ElementTree(r).write(arq, encoding="utf-8")
    return arq


def rodar(comparacao: str, com_sistema: bool, semente: int = 1, duracao: int = DURACAO_S, demanda=None,
          ao_passo=None, passo_s: float = 1.0) -> dict:
    """Uma rodada; devolve as métricas do cenário. `demanda(pasta) -> Path` troca a demanda (animação);
    `ao_passo(estado_semaforo)` é chamado depois de cada passo (captura de quadros); `passo_s` = passo do SUMO."""
    tipo_rede = "actuated" if comparacao == "semaforo" and com_sistema else "static"
    rede = gerar_rede(tipo_rede)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rou = demanda(tmp) if demanda else _demanda(tmp, semente, ambulancia=comparacao == "ambulancia",
                                                    duracao=duracao)
        trip = tmp / "tripinfo.xml"
        traci.start([str(SUMO_PKG / "bin" / "sumo.exe"), "-n", str(rede), "-r", str(rou), "--seed", str(semente),
                     "--tripinfo-output", str(trip), "--device.emissions.probability", "1", "--no-warnings",
                     "--no-step-log", "--time-to-teleport", "300", "--end", str(duracao + 600),
                     "--step-length", str(passo_s)])
        surpreendidos = {"pedestre": set(), "pedestre_reduzida": set()}
        prioridade = False
        try:
            if tipo_rede == "static":
                _programa_fixo()
            trav = _travessias()
            faixas = {f for _, f in trav}
            verde_antes = False
            while traci.simulation.getMinExpectedNumber() > 0 and traci.simulation.getTime() < duracao + 600:
                traci.simulationStep()
                estado = traci.trafficlight.getRedYellowGreenState(TLS)
                verde = any(estado[i] in "Gg" for i, _ in trav)
                na_faixa = [p for p in traci.person.getIDList() if traci.person.getLaneID(p) in faixas]
                # sistema: estende o verde enquanto houver pessoa com mobilidade reduzida sem tempo de terminar
                # (a regra do nó: verde = comprimento ÷ 0,8 m/s)
                if comparacao == "pedestre" and com_sistema and verde:
                    falta = traci.trafficlight.getNextSwitch(TLS) - traci.simulation.getTime()
                    precisa = max((_restante(p) / VEL_REDUZIDA + FOLGA_S for p in na_faixa
                                   if traci.person.getTypeID(p) == "pedestre_reduzida"), default=0)
                    if precisa > falta:
                        traci.trafficlight.setPhaseDuration(TLS, precisa)
                # ambulância com prioridade: verde para a avenida quando ela está a < 150 m — sem cortar a faixa
                if comparacao == "ambulancia" and com_sistema:
                    perto = any(v.startswith("amb") and traci.vehicle.getRoadID(v) == "OC"
                                and traci.vehicle.getLanePosition(v) > BRACO_M - 150
                                for v in traci.vehicle.getIDList())
                    if perto and not na_faixa:
                        traci.trafficlight.setRedYellowGreenState(TLS, _estado_avenida())
                        prioridade = True
                    elif prioridade and not perto:
                        traci.trafficlight.setProgram(TLS, "0")
                        _programa_fixo()
                        prioridade = False
                if verde_antes and not verde:          # quem ainda está na faixa quando o verde dela acaba
                    for p in na_faixa:
                        surpreendidos[traci.person.getTypeID(p)].add(p)
                verde_antes = verde
                if ao_passo:
                    ao_passo(traci.trafficlight.getRedYellowGreenState(TLS))
        finally:
            traci.close()
        return _metricas(trip, surpreendidos)


def _restante(p: str) -> float:
    return max(0.0, traci.lane.getLength(traci.person.getLaneID(p)) - traci.person.getLanePosition(p))


def _estado_avenida() -> str:
    """Verde para os movimentos que saem do oeste (OC, por onde vem a ambulância); vermelho no resto."""
    links = traci.trafficlight.getControlledLinks(TLS)
    return "".join("G" if l and l[0][0].startswith("OC_") else "r" for l in links)


def _metricas(trip: Path, surpreendidos: dict) -> dict:
    r = ET.parse(trip).getroot()
    carros = [t for t in r.iter("tripinfo") if t.get("vType") == "carro"]
    amb = [float(t.get("duration")) for t in r.iter("tripinfo") if t.get("vType") == "ambulancia"]
    pessoas = list(r.iter("personinfo"))
    espera = [sum(float(w.get("waitingTime", 0)) for w in p.iter("walk")) for p in pessoas]
    n_red = sum(1 for p in pessoas if p.get("type") == "pedestre_reduzida")
    co2 = [float(t.find("emissions").get("CO2_abs")) / 1000 for t in carros if t.find("emissions") is not None]

    def media(xs):
        return sum(xs) / len(xs) if xs else float("nan")
    return {
        "carros": len(carros),
        "atraso_medio_carro_s": round(media([float(t.get("timeLoss")) for t in carros]), 1),
        "co2_medio_g_por_carro": round(media(co2), 1),
        "pessoas": len(pessoas), "pessoas_reduzida": n_red,
        "espera_media_pedestre_s": round(media(espera), 1),
        "surpreendidos_reduzida": len(surpreendidos["pedestre_reduzida"]),
        "surpreendidos_reduzida_pct": round(100 * len(surpreendidos["pedestre_reduzida"]) / n_red, 1) if n_red else 0.0,
        "surpreendidos_comum": len(surpreendidos["pedestre"]),
        "tempo_ambulancia_s": round(media(amb), 1) if amb else None,           # média das 6 da rodada
        "tempo_ambulancia_max_s": round(max(amb), 1) if amb else None,
    }


def rodar_tudo(sementes=(1, 2, 3, 4, 5), duracao: int = DURACAO_S) -> list[dict]:
    linhas = []
    for comp in ("pedestre", "semaforo", "ambulancia"):
        for sis in (False, True):
            for s in sementes:
                linhas.append({"comparacao": comp, "sistema": "com" if sis else "sem", "semente": s,
                               **rodar(comp, sis, s, duracao)})
    return linhas


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    EVID.mkdir(parents=True, exist_ok=True)
    linhas = rodar_tudo()
    with open(EVID / "estudo_a_rodadas.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} rodadas em {EVID / 'estudo_a_rodadas.csv'}")


if __name__ == "__main__":
    main()
