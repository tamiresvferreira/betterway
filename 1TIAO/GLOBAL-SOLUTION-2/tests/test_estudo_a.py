"""Estudo A no SUMO (src/simulacao/estudo_a.py). Usa o simulador de verdade: python -m pytest tests/test_estudo_a.py -m slow"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "simulacao"))
import estudo_a as a  # noqa: E402

DUR = 600


@pytest.mark.slow
def test_rede_tem_faixa_de_16m_e_verde_de_19s():
    a.traci.start([str(a.SUMO_PKG / "bin" / "sumo.exe"), "-n", str(a.gerar_rede("static")), "--no-warnings",
                   "--no-step-log"])
    try:
        a._programa_fixo()
        trav = a._travessias()
        assert len(trav) == 2 and all(15.5 < a.traci.lane.getLength(f) < 17 for _, f in trav)
        fases = a.traci.trafficlight.getAllProgramLogics(a.TLS)[0].phases
        verdes = [f.duration for f in fases if any(f.state[i] in "Gg" for i, _ in trav)]
        assert a.VERDE_PEDESTRE_S in verdes
    finally:
        a.traci.close()


@pytest.mark.slow
def test_extensao_protege_quem_tem_mobilidade_reduzida():
    sem, com = a.rodar("pedestre", False, 1, DUR), a.rodar("pedestre", True, 1, DUR)
    assert sem["pessoas_reduzida"] > 0 and sem["surpreendidos_reduzida"] > 0
    assert com["surpreendidos_reduzida"] == 0
    assert com["carros"] == sem["carros"]                       # mesma demanda nas duas rodadas


@pytest.mark.slow
def test_prioridade_nao_atrasa_a_ambulancia():
    sem, com = a.rodar("ambulancia", False, 1, DUR), a.rodar("ambulancia", True, 1, DUR)
    assert com["tempo_ambulancia_s"] <= sem["tempo_ambulancia_s"]
    assert com["tempo_ambulancia_max_s"] <= sem["tempo_ambulancia_max_s"]


@pytest.mark.slow
def test_metricas_completas_e_coerentes():
    m = a.rodar("semaforo", True, 2, DUR)
    for k in ("carros", "atraso_medio_carro_s", "co2_medio_g_por_carro", "espera_media_pedestre_s"):
        assert m[k] == m[k] and m[k] >= 0                       # não é NaN nem negativo
    assert m["carros"] > 100


# ---------------------------------------------------------------- revisão conjunta
@pytest.mark.slow
def test_demanda_em_ordem_de_partida(tmp_path):
    """Revisão: elementos fora de ordem de partida são DESCARTADOS pelo SUMO (32 de 87 pessoas na rodada da
    ambulância). A rodada da ambulância tem de ter as mesmas pessoas que a de pedestre, mesma semente."""
    import xml.etree.ElementTree as ET
    rou = a._demanda(tmp_path, 1, ambulancia=True, duracao=900)
    partidas = [float(e.get("depart", e.get("begin", 0))) for e in ET.parse(rou).getroot()
                if e.tag in ("vehicle", "trip", "person", "flow")]
    assert partidas == sorted(partidas)
    amb, ped = a.rodar("ambulancia", False, 1, 900), a.rodar("pedestre", False, 1, 900)
    assert amb["pessoas"] == ped["pessoas"]


@pytest.mark.slow
def test_ciclo_do_tempo_fixo_tem_cerca_de_75s():
    """Revisão: as fases curtas de transição (5 s) não podem virar 40 s (o ciclo ia a 145 s)."""
    a.traci.start([str(a.SUMO_PKG / "bin" / "sumo.exe"), "-n", str(a.gerar_rede("static")), "--no-warnings",
                   "--no-step-log"])
    try:
        a._programa_fixo()
        fases = a.traci.trafficlight.getAllProgramLogics(a.TLS)[0].phases
        assert 70 <= sum(f.duration for f in fases) <= 80
        assert sorted(f.duration for f in fases) == [3, 3, 5, 5, a.VERDE_PEDESTRE_S, a.VERDE_AVENIDA_S]
    finally:
        a.traci.close()


@pytest.mark.slow
def test_animacao_pedestre_mostra_o_que_a_legenda_diz():
    """A cena da animação: sem o sistema o verde do pedestre fecha com a pessoa lenta na faixa; com ele, não."""
    import animacao_estudo_a as an

    def lenta_na_faixa_com_vermelho(quadros):
        return any(not q["verde_ped"] and any(tipo != "pedestre" and na_faixa for _, _, tipo, na_faixa in q["pessoas"])
                   for q in quadros)

    assert lenta_na_faixa_com_vermelho(an.capturar("pedestre", False))
    assert not lenta_na_faixa_com_vermelho(an.capturar("pedestre", True))
