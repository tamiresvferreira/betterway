"""Laço da central (src/central/central.py) com MQTT e risco falsos e banco em memória."""
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

import central as c
import decisao as d

SCHEMA = Path(__file__).resolve().parents[1] / "src" / "central" / "schema.sql"
SEG_10H = datetime(2026, 11, 16, 10, 0)


def _risco_falso(lat, lon, quando, chuva_mm):
    return {"probabilidade_atropelamento_1h": 0.008, "nivel": "medio"}


@pytest.fixture
def ambiente():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    enviados = []

    def publicar(cmd):
        enviados.append(cmd)
        return True

    return c.Central(con, publicar=publicar, risco_fn=_risco_falso), con, enviados


def _alertas(con):
    return con.execute("SELECT modo, motivo, risco, enviado, cluster_id, timestamp FROM alertas ORDER BY id").fetchall()


def test_publica_na_mudanca_e_reenvia_a_cada_30s(ambiente):
    ce, con, env = ambiente
    for t in range(0, 61):
        ce.passo(d.Entradas(quando=SEG_10H), t)
    assert [x["modo"] for x in env] == ["normal", "normal", "normal"]      # t = 0, 30, 60
    ce.passo(d.Entradas(quando=SEG_10H, chuva_mm_h=6.0, chuva_simulada=True), 61)
    assert env[-1]["modo"] == "chuva" and env[-1]["alagamento"] is False


def test_alerta_so_na_troca_de_modo_ou_alagamento(ambiente):
    ce, con, env = ambiente
    ce.passo(d.Entradas(quando=SEG_10H), 0)
    ce.passo(d.Entradas(quando=SEG_10H), 31)
    ce.passo(d.Entradas(quando=SEG_10H, chuva_mm_h=6.0, chuva_simulada=True), 32)
    ce.passo(d.Entradas(quando=SEG_10H, chuva_mm_h=6.5, chuva_simulada=True), 33)
    ce.passo(d.Entradas(quando=SEG_10H, chuva_mm_h=12.0, chuva_simulada=True), 34)
    a = _alertas(con)
    assert [x[0] for x in a] == ["normal", "chuva", "chuva"]
    modo, motivo, risco, enviado, cluster, ts = a[1]
    assert "SIMULADA" in motivo and "medio" in motivo and risco == 0.008 and enviado == 1
    assert cluster == 139 and ts.endswith("-03:00")


def test_ambulancia_reenvia_eta_a_cada_10s(ambiente):
    ce, con, env = ambiente
    for t in range(0, 25):
        ce.passo(d.Entradas(quando=SEG_10H, ambulancia_eta_s=60 - t), t)
    assert [x["eta_s"] for x in env if x["modo"] == "ambulancia"] == [60, 50, 40]


def test_falha_no_envio_fica_registrada():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    ce = c.Central(con, publicar=lambda cmd: False, risco_fn=_risco_falso)
    ce.passo(d.Entradas(quando=SEG_10H), 0)
    assert _alertas(con)[0][3] == 0


def test_cenario_demo_passa_por_todos_os_modos():
    seq = []
    for t in range(0, c.DURACAO_DEMO_S + 1):
        e, _hora = c.entradas_demo(t, chuva_real=0.0, pessoas_visao=48)
        r = d.decidir(e)
        chave = (r.modo, r.campos.get("alagamento"), bool(r.campos.get("fim")))
        if not seq or seq[-1] != chave:
            seq.append(chave)
    assert seq == [("normal", None, False), ("escola", None, False), ("pedestre", None, False),
                   ("chuva", False, False), ("chuva", True, False), ("ambulancia", None, False),
                   ("ambulancia", None, True), ("normal", None, False)]


def test_demo_usa_chuva_real_quando_chove_de_verdade():
    e, _ = c.entradas_demo(160, chuva_real=4.0, pessoas_visao=0)
    assert e.chuva_mm_h == 4.0 and not e.chuva_simulada
    e2, _ = c.entradas_demo(160, chuva_real=None, pessoas_visao=0)
    assert e2.chuva_simulada and e2.chuva_mm_h == 6.0


# ---------------------------------------------------------------- revisão conjunta
def test_fim_da_ambulancia_e_enviado_mesmo_se_o_laco_pular_a_janela(ambiente):
    """Revisão: o 'fim' só existia numa janela de 1 s; um passo atrasado (publish lento) pulava direto para normal."""
    ce, con, env = ambiente
    ce.passo(d.Entradas(quando=SEG_10H, ambulancia_eta_s=3), 0)
    ce.passo(d.Entradas(quando=SEG_10H), 6)                 # a janela do 'passou' foi pulada
    assert [(x["modo"], x.get("fim", False)) for x in env] == [("ambulancia", False), ("ambulancia", True),
                                                               ("normal", False)]


def test_agora_e_horario_de_sao_paulo():
    assert c.agora().utcoffset().total_seconds() == -3 * 3600
