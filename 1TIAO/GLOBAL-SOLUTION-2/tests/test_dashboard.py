"""Painel Streamlit (src/dashboard/app.py): abre com um banco pequeno de exemplo e sem banco, sem erro."""
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py"
SCHEMA = Path(__file__).resolve().parents[1] / "src" / "central" / "schema.sql"


@pytest.fixture
def banco(tmp_path):
    db = tmp_path / "exemplo.db"
    con = sqlite3.connect(db)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    for col in ("n_escolas_300m INTEGER", "n_semaforos_150m INTEGER"):
        con.execute(f"ALTER TABLE clusters ADD COLUMN {col}")
    con.executemany(
        "INSERT INTO clusters (cluster_id, lat_centro, lon_centro, n_fatais, n_nao_fatais, peso, extensao_m, indice_cet,"
        " rank_prioridade, rank_urbano, n_coords_distintas, pct_via_urbana, via_principal, eps_m, min_samples, criado_em,"
        " n_escolas_300m, n_semaforos_150m) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(139, -23.5418, -46.6161, 2, 20, 26, 150, 5.8, 40, 26, 12, 1.0, "AVENIDA RANGEL PESTANA", 100, 8, "x", 0, 4),
         (1, -23.60, -46.70, 5, 30, 45, 300, 6.7, 1, 1, 20, 1.0, "AVENIDA X", 100, 8, "x", 2, 1)])
    con.execute("INSERT INTO eventos (timestamp, origem, cluster_id, tipo, payload_json, chave) VALUES "
                "('2026-11-17T08:00:00-03:00', 'esp32', 139, 'botao_recusado_ambulancia', '{}', 'k1')")
    con.execute("INSERT INTO alertas (timestamp, cluster_id, modo, motivo, risco, enviado) VALUES "
                "('2026-11-17T08:00:00-03:00', 139, 'chuva', 'chuva 6,0 mm/h (SIMULADA)', 0.008, 1)")
    con.commit()
    con.close()
    return db


def _abrir(monkeypatch, db):
    monkeypatch.setenv("VIA_SEGURA_DB", str(db))
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    return at


def test_painel_abre_com_tres_abas(monkeypatch, banco):
    at = _abrir(monkeypatch, banco)
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Mapa de risco", "Indicadores", "Eventos e alertas"]
    textos = " ".join(str(m.value) for m in at.markdown) + " ".join(str(c.value) for c in at.caption)
    assert "Largo da Concórdia" in textos


def test_painel_sem_banco_avisa_e_nao_quebra(monkeypatch, tmp_path):
    at = _abrir(monkeypatch, tmp_path / "nao_existe.db")
    assert not at.exception
    assert any("banco" in str(w.value).lower() for w in at.warning)
