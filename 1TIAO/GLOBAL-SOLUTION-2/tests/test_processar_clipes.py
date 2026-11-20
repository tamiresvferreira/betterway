"""Clipes sintéticos (Veo 3): categoria pelo nome e avaliação esperado × obtido (src/visao/processar_clipes.py)."""
import pytest

import processar_clipes as pc
import visao as v


def _ev(tipo, **payload):
    return v.Evento(tipo, 0, 1, None, payload)


def test_categoria_pelo_nome():
    assert pc.categoria_do_clipe("cadeirante_01") == "cadeirante"
    assert pc.categoria_do_clipe("normal_noite_01.mp4") == "normal_noite"
    assert pc.categoria_do_clipe("suspeita_acidente_02.mp4") == "suspeita_acidente"
    with pytest.raises(ValueError):
        pc.categoria_do_clipe("meu_video.mp4")


def test_auxilio_certo_acerta_e_falso_alarme_erra():
    assert pc.avaliar("cadeirante", [_ev("pcd_na_faixa", auxilio="wheelchair")])["acerto"]
    assert not pc.avaliar("cadeirante", [])["acerto"]
    assert not pc.avaliar("armadilha", [_ev("pcd_na_faixa", auxilio="wheelchair")])["acerto"]
    assert pc.avaliar("armadilha", [_ev("pedestre_na_faixa")])["acerto"]


def test_suspeita_e_conflito():
    assert pc.avaliar("suspeita_acidente", [_ev("suspeita_acidente")])["acerto"]
    assert not pc.avaliar("suspeita_acidente", [])["acerto"]
    assert not pc.avaliar("normal", [_ev("suspeita_acidente")])["acerto"]
    assert pc.avaliar("conflito", [_ev("conflito_veiculo_pedestre")])["acerto"]
    assert not pc.avaliar("conflito", [])["acerto"]


def test_todas_as_categorias_da_lista_de_clipes_existem():
    for c in ["normal", "normal_noite", "cadeirante", "andador", "muleta", "bengala", "surpreendido", "conflito",
              "chuva", "alagamento", "escola", "ambulancia", "suspeita_acidente", "suspeita_bike", "armadilha"]:
        assert c in pc.ESPERADO


@pytest.mark.slow
def test_processar_um_clipe_curto_gera_video_borrado_e_eventos(tmp_path, monkeypatch):
    """30 quadros de um vídeo real de cadeirante, com nome de clipe; faixa = a metade de baixo da imagem."""
    import json
    import shutil
    import sqlite3
    original = pc.RAIZ / "data" / "raw" / "video" / "cadeirante_pexels_6646677.mp4"
    if not original.exists() or not (pc.MODELS / "pcd_yolo11s.pt").exists():
        pytest.skip("vídeo ou modelo ajustado fora do Git")
    clipe = tmp_path / "cadeirante_01.mp4"
    shutil.copy(original, clipe)
    _, w, h, _ = v.ler_video(clipe)
    faixa = tmp_path / "faixa.json"
    faixa.write_text(json.dumps({"poligono": [[0, h // 2], [w, h // 2], [w, h], [0, h]], "resolucao": [w, h],
                                 "lado_a": [3, 0], "lado_b": [1, 2], "comprimento_m": 8.0}), encoding="utf-8")
    monkeypatch.setattr(pc, "FAIXA_BASE", faixa)
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, origem TEXT NOT "
                "NULL, cluster_id INTEGER, tipo TEXT NOT NULL, valor REAL, payload_json TEXT)")
    eventos, av = pc.processar(clipe, con, max_quadros=30, saida_dir=tmp_path / "saida")
    assert (tmp_path / "saida" / "cadeirante_01_anotado.mp4").stat().st_size > 10_000
    assert json.loads((tmp_path / "saida" / "cadeirante_01_eventos.json").read_text(encoding="utf-8")) is not None
    assert av["clipe"] == "cadeirante_01" and av["categoria"] == "cadeirante"
    assert con.execute("SELECT count(*) FROM eventos").fetchone()[0] == len(eventos)
