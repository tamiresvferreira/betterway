"""Leitura da situação (src/operador/leitura.py): a conclusão vem da soma das evidências, cada uma com a sua fonte."""
from padrao import Padrao

import leitura as lt

REPETE = Padrao(53, 12, None, 2.5, True, "12 dos 53 …")
NAO_REPETE = Padrao(53, 1, None, 0.2, False, "1 dos 53 …")
CAM_COM_CONFLITO = lt.Camera(pessoas_na_faixa=31, conflitos=2, mobilidade_reduzida=1, fonte="demo")
CAM_TRANQUILA = lt.Camera(pessoas_na_faixa=4, conflitos=0, mobilidade_reduzida=0, fonte="demo")


def test_historico_camera_e_chuva_dao_padrao_se_repetindo():
    l = lt.ler(REPETE, CAM_COM_CONFLITO, chuva_mm_h=5.0, risco_vezes_local=1.0)
    assert l.nivel == "padrao"
    assert [e.fonte for e in l.evidencias] == ["Infosiga-SP", "Open-Meteo", "Visão computacional", "Modelo de risco"]
    assert l.recomendacao and l.titulo


def test_so_historico_e_camera_e_atencao():
    assert lt.ler(REPETE, CAM_COM_CONFLITO, chuva_mm_h=0.0, risco_vezes_local=1.0).nivel == "atencao"


def test_uma_evidencia_sozinha_nao_conclui():
    assert lt.ler(REPETE, CAM_TRANQUILA, chuva_mm_h=0.0, risco_vezes_local=1.0).nivel == "normal"
    assert lt.ler(NAO_REPETE, CAM_COM_CONFLITO, chuva_mm_h=0.0, risco_vezes_local=1.0).nivel == "normal"


def test_camera_e_risco_acima_do_normal_sem_historico_e_atencao():
    assert lt.ler(NAO_REPETE, CAM_COM_CONFLITO, chuva_mm_h=0.0, risco_vezes_local=1.8).nivel == "atencao"


def test_falta_de_dado_aparece_como_sem_dado():
    l = lt.ler(REPETE, None, chuva_mm_h=None, risco_vezes_local=None)
    assert l.nivel == "normal"
    assert sum(1 for e in l.evidencias if e.estado == "sem_dado") == 3


def test_linha_do_tempo_so_grava_quando_a_conclusao_muda():
    import sqlite3
    from datetime import datetime, timedelta
    con = sqlite3.connect(":memory:")
    lt.migrar(con)
    t0 = datetime(2026, 11, 18, 17, 0)
    a = lt.ler(REPETE, CAM_COM_CONFLITO, chuva_mm_h=5.0, risco_vezes_local=1.0)
    b = lt.ler(REPETE, CAM_TRANQUILA, chuva_mm_h=0.0, risco_vezes_local=1.0)
    for i, l in enumerate([a, a, b, b, a]):
        lt.registrar(con, l, t0 + timedelta(minutes=i), simulado=False)
    assert [r["nivel"] for r in lt.historico(con)] == ["padrao", "normal", "padrao"]
