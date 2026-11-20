"""Gravador dos eventos do nó ESP32 na tabela eventos (src/central/gravador_mqtt.py)."""
import json
import sqlite3
from pathlib import Path

import pytest

import gravador_mqtt as g

SCHEMA = Path(__file__).resolve().parents[1] / "src" / "central" / "schema.sql"


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA.read_text(encoding="utf-8"))
    yield c
    c.close()


def _ev(seq=1, tipo="pedido_recusado_ambulancia"):
    return json.dumps({"v": 1, "tipo": tipo, "seq": seq, "boot": "b9", "detalhe": {"eta_s": 20}}).encode()


def test_grava_evento_com_origem_cluster_chave(con):
    assert g.processar(con, _ev()) == "gravado"
    origem, cluster, tipo, payload, chave, ts = con.execute(
        "SELECT origem, cluster_id, tipo, payload_json, chave, timestamp FROM eventos").fetchone()
    assert (origem, cluster, tipo) == ("esp32", 139, "pedido_recusado_ambulancia")
    assert chave == "esp32:largo-concordia:b9:1" and ts.endswith("-03:00")
    p = json.loads(payload)
    assert p["demonstracao"] is True and p["detalhe"]["eta_s"] == 20


def test_repetido_nao_duplica(con):
    g.processar(con, _ev())
    assert g.processar(con, _ev()) == "repetido"
    assert con.execute("SELECT COUNT(*) FROM eventos").fetchone()[0] == 1


def test_fora_de_ordem_grava_os_dois(con):
    assert g.processar(con, _ev(seq=5)) == "gravado" and g.processar(con, _ev(seq=4)) == "gravado"


def test_lixo_nao_derruba(con):
    for ruim in (b"\xff\x00", b"[1,2]", b'{"v":1}', _ev(tipo="nada"), b"", b"null"):
        assert g.processar(con, ruim).startswith("invalido")
    assert g.processar(con, _ev(seq=2)) == "gravado"


def test_mensagem_maliciosa_nao_derruba(con):
    """Revisão: broker público — qualquer um publica. JSON profundo demais (RecursionError) não pode matar o gravador."""
    assert g.processar(con, b"[" * 100000).startswith("invalido")
    assert g.processar(con, _ev(seq=7)) == "gravado"


def test_erro_do_banco_nao_derruba():
    import sqlite3
    sem_tabela = sqlite3.connect(":memory:")
    assert g.processar(sem_tabela, _ev()).startswith("erro")
