"""Fontes de entrada da central (src/central/fontes.py)."""
import sqlite3
from datetime import datetime
from pathlib import Path

import fontes as f

SCHEMA = Path(__file__).resolve().parents[1] / "src" / "central" / "schema.sql"


def test_chuva_open_meteo_pega_a_hora_certa():
    resposta = {"hourly": {"time": ["2026-11-16T07:00", "2026-11-16T08:00", "2026-11-16T09:00"],
                           "precipitation": [0.0, 3.2, 1.0]}}
    urls = []

    def obter(u):
        urls.append(u)
        return resposta

    v = f.chuva_prevista_mm_h(-23.54, -46.61, datetime(2026, 11, 16, 8, 40), obter=obter)
    assert v == 3.2 and "latitude=-23.54" in urls[0] and "precipitation" in urls[0]


def test_chuva_falha_devolve_none():
    def falha(_):
        raise OSError("sem rede")

    assert f.chuva_prevista_mm_h(-23.54, -46.61, datetime(2026, 11, 16, 8), obter=falha) is None
    vazio = {"hourly": {"time": [], "precipitation": []}}
    assert f.chuva_prevista_mm_h(-23.54, -46.61, datetime(2030, 1, 1, 8), obter=lambda u: vazio) is None


def test_eta_ambulancia_decresce_e_nao_fica_negativo():
    etas = [f.eta_ambulancia(t, 750, 40) for t in (0, 30, 67, 100)]
    assert etas[0] == 67.5 and etas == sorted(etas, reverse=True) and etas[-1] == 0


def test_pessoas_na_faixa_do_banco():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    linhas = [("2026-11-16T08:00:00-03:00", "yolo", "pedestre_na_faixa", '{"video_id": "v1"}', "k1"),
              ("2026-11-16T08:00:30-03:00", "yolo", "pedestre_na_faixa", '{"video_id": "v1"}', "k2"),
              ("2026-11-16T07:00:00-03:00", "yolo", "pedestre_na_faixa", '{"video_id": "v2"}', "k3"),
              ("2026-11-16T08:00:40-03:00", "yolo", "travessia", '{"video_id": "v1"}', "k4")]
    con.executemany("INSERT INTO eventos (timestamp, origem, tipo, payload_json, chave) VALUES (?,?,?,?,?)", linhas)
    assert f.pessoas_na_faixa(con, video_id="v1") == 2
    assert f.pessoas_na_faixa(con, desde=datetime.fromisoformat("2026-11-16T08:00:10-03:00")) == 1
    assert f.pessoas_na_faixa(sqlite3.connect(":memory:")) == 0          # banco sem tabela: 0, sem cair
