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
