"""Testes do módulo de visão na faixa de pedestres (src/visao/visao.py).

Todos usam detecções escritas à mão: rodam sem GPU e sem baixar pesos. O teste com o YOLO-World real é marcado
@pytest.mark.slow. Rodar a partir de 1TIAO/GLOBAL-SOLUTION-2/:  python -m pytest tests -q -m "not slow"
"""
import pytest

import visao as vs

TRAPEZIO = [(100, 600), (1180, 600), (900, 300), (380, 300)]


def faixa_de(poligono, resolucao=(1280, 720), lado_a=(0, 1), lado_b=(2, 3), comprimento_m=12.0):
    return vs.Faixa.de_dict({"poligono": poligono, "resolucao": list(resolucao), "lado_a": list(lado_a),
                             "lado_b": list(lado_b), "comprimento_m": comprimento_m})


# ---------------------------------------------------------------- Tarefa 1: geometria da faixa
def test_trapezio_em_perspectiva():
    f = faixa_de(TRAPEZIO)
    assert f.contem((640, 450)) is True
    assert f.contem((640, 250)) is False
    assert f.contem((150, 320)) is False


def test_poligono_concavo():
    u = [(0, 0), (300, 0), (300, 300), (200, 300), (200, 100), (100, 100), (100, 300), (0, 300)]
    f = faixa_de(u, resolucao=(400, 400), lado_a=(0, 1), lado_b=(2, 3))
    assert f.contem((150, 200)) is False      # no vão do "U"
    assert f.contem((50, 200)) is True
    assert f.contem((250, 200)) is True


def test_sentido_dos_vertices_nao_importa():
    a, b = faixa_de(TRAPEZIO), faixa_de(list(reversed(TRAPEZIO)))
    for p in [(640, 450), (640, 250), (150, 320)]:
        assert a.contem(p) == b.contem(p)


def test_poligono_invalido():
    with pytest.raises(ValueError, match="pelo menos 3"):
        faixa_de([(0, 0), (10, 10)])
    with pytest.raises(ValueError, match="se cruzam"):
        faixa_de([(0, 0), (100, 100), (100, 0), (0, 100)])


def test_ponto_da_pessoa_e_a_base():
    assert vs.ponto_da_pessoa((600, 200, 680, 460)) == (640.0, 460.0)
    f = faixa_de(TRAPEZIO)
    assert f.contem(vs.ponto_da_pessoa((600, 200, 680, 460))) is True   # pés dentro
    assert f.contem((640, 200)) is False                                # cabeça fora, por perspectiva


def test_borda_conta_como_dentro():
    assert faixa_de(TRAPEZIO).contem((640, 600)) is True


def test_reescala_mesma_proporcao():
    f = faixa_de(TRAPEZIO).para_resolucao(1920, 1080)
    assert f.poligono == [(150.0, 900.0), (1770.0, 900.0), (1350.0, 450.0), (570.0, 450.0)]
    assert f.resolucao == (1920, 1080)


def test_proporcao_diferente_recusa():
    with pytest.raises(ValueError, match="proporção"):
        faixa_de(TRAPEZIO).para_resolucao(1440, 1080)


def test_json_sem_chave():
    with pytest.raises(ValueError, match="comprimento_m"):
        vs.Faixa.de_dict({"poligono": TRAPEZIO, "resolucao": [1280, 720], "lado_a": [0, 1], "lado_b": [2, 3]})


# ---------------------------------------------------------------- Tarefa 2: travessias
# Faixa de teste: retângulo 100 × 1200 px; calçada A = aresta de cima (y = 0), B = aresta de baixo (y = 1200); 12 m.
RET = [(0, 0), (100, 0), (100, 1200), (0, 1200)]


def faixa_ret():
    return faixa_de(RET, resolucao=(1280, 1280), lado_a=(0, 1), lado_b=(2, 3), comprimento_m=12.0)


def trajeto(track_id, ys, x=50, quadro0=0, classe="person"):
    """Uma detecção por quadro com os pés em (x, y); None = pessoa sumiu naquele quadro."""
    return [vs.Deteccao(quadro0 + i, classe, (x - 20, y - 100, x + 20, y), 0.9, track_id)
            for i, y in enumerate(ys) if y is not None]


def atravessa(n_dentro, antes=3, depois=3, y0=10, y1=1190):
    """Fora em A (y=-50), n_dentro quadros de y0 a y1, fora em B (y=1250)."""
    passo = (y1 - y0) / max(n_dentro - 1, 1)
    return [-50] * antes + [y0 + passo * i for i in range(n_dentro)] + [1250] * depois


def test_travessia_simples():
    t = vs.travessias(trajeto(1, atravessa(300)), faixa_ret(), fps=30)
    assert len(t) == 1
    assert t[0].status == "concluida"
    assert t[0].duracao_s == pytest.approx(10.0, abs=0.2)
    assert t[0].velocidade_ms == pytest.approx(1.2, abs=0.03)
    assert (t[0].lado_entrada, t[0].lado_saida) == ("A", "B")


def test_tremor_na_borda():
    ys = [10 if i % 2 == 0 else -10 for i in range(20)] + [-50] * 10
    t = vs.travessias(trajeto(1, ys), faixa_ret(), fps=30)
    assert [x for x in t if x.status == "concluida"] == []


def test_oclusao_curta_mantem_uma_travessia():
    ys = atravessa(300)
    ys[150:170] = [None] * 20                     # 20 quadros = 0,67 s escondida atrás de um ônibus
    t = vs.travessias(trajeto(1, ys), faixa_ret(), fps=30)
    assert [x.status for x in t] == ["concluida"]


def test_troca_de_id():
    ys = atravessa(300)
    meio = 150
    dets = trajeto(1, ys[:meio]) + trajeto(2, ys[meio:], quadro0=meio)
    t = sorted(vs.travessias(dets, faixa_ret(), fps=30), key=lambda x: x.track_id)
    assert [x.status for x in t] == ["nao_concluida", "inicio_desconhecido"]
    assert all(x.duracao_s <= len(ys) / 30 for x in t)


def test_retorno():
    ys = [-50] * 3 + [10 + 5 * i for i in range(60)] + [-50] * 5   # entra por A e volta para A
    t = vs.travessias(trajeto(1, ys), faixa_ret(), fps=30)
    assert [x.status for x in t] == ["retorno"]


def test_ja_dentro_no_primeiro_quadro():
    ys = [600 + 2 * i for i in range(200)] + [1250] * 5
    t = vs.travessias(trajeto(1, ys), faixa_ret(), fps=30)
    assert [x.status for x in t] == ["inicio_desconhecido"]


def test_fps_muda_a_duracao():
    dets = trajeto(1, atravessa(300))
    assert vs.travessias(dets, faixa_ret(), fps=15)[0].duracao_s == pytest.approx(20.0, abs=0.3)
    assert vs.travessias(dets, faixa_ret(), fps=30)[0].duracao_s == pytest.approx(10.0, abs=0.2)


@pytest.mark.parametrize("fps", [0, -1, None])
def test_fps_invalido(fps):
    with pytest.raises(ValueError, match="fps"):
        vs.travessias(trajeto(1, atravessa(300)), faixa_ret(), fps=fps)


def test_varias_pessoas():
    dets = trajeto(1, atravessa(300), x=30) + trajeto(2, atravessa(450), x=70)
    t = {x.track_id: x for x in vs.travessias(dets, faixa_ret(), fps=30)}
    assert t[1].duracao_s == pytest.approx(10.0, abs=0.2)
    assert t[2].duracao_s == pytest.approx(15.0, abs=0.2)


def test_parado_acima_do_teto():
    t = vs.travessias(trajeto(1, atravessa(130 * 30)), faixa_ret(), fps=30)
    assert [x.status for x in t] == ["acima_do_teto"]


def test_abaixo_1_2_ms():
    t = vs.travessias(trajeto(1, atravessa(450)), faixa_ret(), fps=30)[0]
    assert t.velocidade_ms == pytest.approx(0.8, abs=0.02)
    assert t.abaixo_1_2_ms is True


def test_track_none_e_ignorado():
    dets = [vs.Deteccao(i, "person", (30, 0, 70, 600), 0.9, None) for i in range(50)]
    assert vs.travessias(dets, faixa_ret(), fps=30) == []


def test_deteccao_duplicada_no_quadro():
    dets = trajeto(1, atravessa(300))
    t = vs.travessias(dets + dets, faixa_ret(), fps=30)
    assert len(t) == 1 and t[0].duracao_s == pytest.approx(10.0, abs=0.2)


def test_pcd_marca_a_travessia():
    t = vs.travessias(trajeto(1, atravessa(300)), faixa_ret(), fps=30, pcd_ids={1})
    assert t[0].pcd is True


# ---------------------------------------------------------------- Tarefa 3: PCD, conflitos e bloqueios
def D(classe, caixa, track_id=None, quadro=0, conf=0.9):
    return vs.Deteccao(quadro, classe, caixa, conf, track_id)


def test_cadeira_vazia():
    assert vs.associar_auxilios([D("wheelchair", (95, 170, 165, 260))]) == {}


def test_acompanhante():
    sentada = D("person", (100, 100, 160, 250), 1)          # cobre 76% da cadeira
    empurrando = D("person", (140, 90, 200, 250), 2)        # cobre 32% (passa do limiar, mas é menor)
    cadeira = D("wheelchair", (95, 170, 165, 260))
    assert vs.associar_auxilios([sentada, empurrando, cadeira]) == {1: "wheelchair"}


def test_limiar_relativo_ao_tamanho():
    pequena, grande = D("person", (500, 500, 520, 550), 1), D("person", (100, 100, 200, 350), 2)
    cad_pequena, cad_grande = D("wheelchair", (498, 530, 522, 555)), D("wheelchair", (95, 250, 205, 360))
    assert vs.associar_auxilios([pequena, grande, cad_pequena, cad_grande]) == {1: "wheelchair", 2: "wheelchair"}
    deslocada = D("wheelchair", (538, 530, 562, 555))       # 40 px ao lado da pessoa pequena
    assert vs.associar_auxilios([pequena, deslocada]) == {}


def _com_auxilio(n_quadros_com, total=20, classe="wheelchair", conf=0.9):
    dets = []
    for q in range(total):
        dets.append(vs.Deteccao(q, "person", (100, 100, 160, 250), 0.9, 1))
        if q < n_quadros_com:
            dets.append(vs.Deteccao(q, classe, (95, 170, 165, 260), conf, None))
    return dets


def test_persistencia_pcd():
    assert vs.pessoas_pcd(_com_auxilio(5)) == {1}
    assert vs.pessoas_pcd(_com_auxilio(1)) == set()


def test_confianca_baixa_ignorada():
    assert vs.pessoas_pcd(_com_auxilio(20, conf=0.2)) == set()


@pytest.mark.parametrize("classe", ["walker", "crutch", "cane"])
def test_outros_auxilios(classe):
    pessoa = D("person", (100, 100, 160, 250), 1)
    assert vs.associar_auxilios([pessoa, D(classe, (95, 170, 165, 260))]) == {1: classe}
    assert vs.associar_auxilios([pessoa, D(classe, (600, 600, 660, 700))]) == {}


def andando(classe, quadros, track_id=7, y0=650):
    """Veículo que se move dentro da faixa de teste: a base desce 10 px por quadro (caixa de 50 px de altura)."""
    q0 = quadros[0]
    return [vs.Deteccao(q, classe, (10, y0 + 10 * (q - q0), 90, y0 + 50 + 10 * (q - q0)), 0.9, track_id) for q in quadros]


def test_conflito_deduplicado():
    dets = [vs.Deteccao(q, "person", (30, 500, 70, 600), 0.9, 1) for q in range(40)]
    dets += andando("car", list(range(40)))
    c = vs.conflitos(dets, faixa_ret(), fps=30)
    assert len(c) == 1 and c[0].track_veiculo == 7 and c[0].track_pedestre == 1


@pytest.mark.parametrize("quadro_carro, esperado", [(39, 1), (40, 0)])
def test_janela_de_conflito(quadro_carro, esperado):
    dets = [vs.Deteccao(q, "person", (30, 500, 70, 600), 0.9, 1) for q in range(10)]          # dentro até o quadro 9
    dets += [vs.Deteccao(q, "person", (30, 1200, 70, 1300), 0.9, 1) for q in range(10, 60)]   # fora (y=1300)
    dets += andando("car", [quadro_carro - 1, quadro_carro])      # 2 quadros: dá para medir o movimento
    assert len(vs.conflitos(dets, faixa_ret(), fps=30)) == esperado


@pytest.mark.parametrize("classe, esperado", [("car", 1), ("motorcycle", 1), ("bus", 1), ("truck", 1), ("bicycle", 0)])
def test_classes_de_veiculo(classe, esperado):
    dets = [vs.Deteccao(q, "person", (30, 500, 70, 600), 0.9, 1) for q in range(5)]
    dets += andando(classe, list(range(5)))
    assert len(vs.conflitos(dets, faixa_ret(), fps=30)) == esperado
    if classe == "bicycle":
        assert vs.contagem_bicicletas(dets, faixa_ret()) == 1


@pytest.mark.parametrize("n, esperado", [(60, 1), (59, 0)])
def test_bloqueio(n, esperado):
    dets = [vs.Deteccao(q, "car", (10, 650, 90, 700), 0.9, 7) for q in range(n)]
    assert len(vs.bloqueios(dets, faixa_ret(), fps=30)) == esperado
    assert vs.conflitos(dets, faixa_ret(), fps=30) == []


def test_veiculo_parado_na_faixa_nao_e_conflito():
    # carro parado (base fixa) com pedestre passando à frente: comportamento correto, não quase-acidente
    dets = [vs.Deteccao(q, "person", (30, 500, 70, 600), 0.9, 1) for q in range(40)]
    dets += [vs.Deteccao(q, "car", (10, 650, 90, 700), 0.9, 7) for q in range(40)]
    assert vs.conflitos(dets, faixa_ret(), fps=30) == []


def test_veiculo_andando_na_faixa_vazia_nao_e_bloqueio():
    assert vs.bloqueios(andando("car", list(range(60))), faixa_ret(), fps=30) == []


def test_severidade_pcd():
    dets = [vs.Deteccao(q, "person", (30, 500, 70, 600), 0.9, 1) for q in range(5)]
    dets += andando("car", list(range(5)))
    assert vs.conflitos(dets, faixa_ret(), fps=30, pcd_ids={1})[0].severidade == "alta"
    assert vs.conflitos(dets, faixa_ret(), fps=30)[0].severidade == "normal"


# ---------------------------------------------------------------- Tarefa 4: privacidade
import inspect
import json

import numpy as np


def ruido(h=200, w=300):
    return np.random.default_rng(0).integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def cabeca(caixa, h_img=200, w_img=300):
    x1, y1, x2, y2 = caixa
    yc = y1 + (y2 - y1) * vs.FRACAO_CABECA
    return (max(int(y1), 0), min(int(round(yc)), h_img), max(int(x1), 0), min(int(x2), w_img))


def borrada(orig, nova, regiao):
    a, b, c, d = regiao
    return nova[a:b, c:d].std() <= vs.LIMIAR_BORRAO * orig[a:b, c:d].std()


def test_todas_as_cabecas():
    img = ruido()
    caixas = [(10, 20, 70, 180), (120, 30, 170, 190), (220, 10, 280, 170)]
    out = vs.borrar(img, [D("person", c, i) for i, c in enumerate(caixas)])
    assert all(borrada(img, out, cabeca(c)) for c in caixas)


def test_caixa_na_borda():
    img = ruido()
    # cabeça cortada pela borda de cima/esquerda e pela borda direita
    out = vs.borrar(img, [D("person", (-20, -10, 40, 150), 1), D("person", (280, 150, 330, 260), 2)])
    assert borrada(img, out, cabeca((-20, -10, 40, 150)))
    assert borrada(img, out, cabeca((280, 150, 330, 260)))
    assert out.shape == img.shape


def test_sem_pessoas_identica():
    img = ruido()
    assert np.array_equal(vs.borrar(img, []), img)
    assert np.array_equal(vs.borrar(img, [D("car", (10, 10, 100, 100), 3)]), img)   # carro: só a placa é borrada


def test_entrada_intacta():
    img = ruido()
    copia = img.copy()
    vs.borrar(img, [D("person", (10, 20, 70, 180), 1)])
    assert np.array_equal(img, copia)


def test_placa_borrada():
    img = ruido()
    out = vs.borrar(img, [D("license plate", (100, 100, 160, 130))])
    assert borrada(img, out, (100, 130, 100, 160))


def test_salvar_quadro_grava_borrado(tmp_path):
    import cv2
    img = ruido()
    caixa = (10, 20, 70, 180)
    caminho = vs.salvar_quadro(img, [D("person", caixa, 1)], tmp_path / "q.png")
    lido = cv2.imread(str(caminho))
    assert borrada(img, lido, cabeca(caixa))


def test_nenhuma_outra_funcao_grava_imagem():
    gravadoras = {"salvar_quadro", "gravar_video_borrado"}
    for nome, f in inspect.getmembers(vs, inspect.isfunction):
        if f.__module__ != vs.__name__ or nome in gravadoras:
            continue
        fonte = inspect.getsource(f)
        assert "imwrite" not in fonte and "VideoWriter" not in fonte, f"{nome} grava imagem sem borrar"


# ---------------------------------------------------------------- Tarefa 5: eventos no banco
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SCHEMA = RAIZ / "src" / "central" / "schema.sql"


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA.read_text(encoding="utf-8"))
    yield c
    c.close()


def _cenario():
    """Travessia simples do id 1 (PCD), conflito do carro 7 com o id 1 e bloqueio do carro 8 depois."""
    f = faixa_ret()
    ys = atravessa(300)
    dets = trajeto(1, ys)
    dets += [vs.Deteccao(q, "wheelchair", (30, ys[q] - 40, 70, ys[q]), 0.9, None) for q in range(3, 13)]  # junto aos pés
    dets += andando("car", list(range(150, 160)))
    dets += [vs.Deteccao(q, "car", (10, 650, 90, 700), 0.9, 8) for q in range(400, 470)]
    pcd = {1}
    return vs.eventos_de(vs.travessias(dets, f, 30, pcd), vs.conflitos(dets, f, 30, pcd), vs.bloqueios(dets, f, 30),
                         pcd, dets, f, 30)


def _contar(con):
    return con.execute("SELECT COUNT(*) FROM eventos").fetchone()[0]


def test_tipos_de_evento():
    tipos = {e.tipo for e in _cenario()}
    assert {"pedestre_na_faixa", "pcd_na_faixa", "travessia", "contagem_minuto", "conflito_veiculo_pedestre",
            "bloqueio_faixa"} <= tipos


def test_idempotencia(con):
    ev = _cenario()
    n1 = vs.gravar_eventos(con, ev, "video_teste")
    n2 = vs.gravar_eventos(con, ev, "video_teste")
    assert n1 == len(ev) and n2 == 0 and _contar(con) == len(ev)


def test_reprocessar_video_substitui_resultado_antigo(con):
    """Rodar de novo com outros parâmetros não pode deixar eventos da execução anterior; outro vídeo fica intacto."""
    antigo = [vs.Evento("pedestre_na_faixa", q, 1, None, {}) for q in (5, 6, 7)]
    novo = [vs.Evento("pedestre_na_faixa", 9, 2, None, {})]
    vs.gravar_eventos(con, antigo, "video_a")
    vs.gravar_eventos(con, antigo, "video_b")
    assert vs.substituir_eventos(con, novo, "video_a") == 1
    chaves = {c for (c,) in con.execute("SELECT chave FROM eventos")}
    assert sum(c.startswith("video_a:") for c in chaves) == 1 and sum(c.startswith("video_b:") for c in chaves) == 3


def test_mesmo_veiculo_dois_pedestres_no_mesmo_quadro(con):
    ev = [vs.Evento("conflito_veiculo_pedestre", 10, 7, None, {"track_pedestre": 1}),
          vs.Evento("conflito_veiculo_pedestre", 10, 7, None, {"track_pedestre": 2})]
    assert vs.gravar_eventos(con, ev, "v") == 2


def test_transacao(con):
    ev = _cenario()
    ruim = ev[:2] + [vs.Evento(None, 5, 1, None, {})] + ev[2:]
    with pytest.raises(sqlite3.IntegrityError):
        vs.gravar_eventos(con, ruim, "video_teste")
    assert _contar(con) == 0


def test_nao_concluida_entra(con):
    t = vs.Travessia(1, 0, 10, 0.4, None, "A", None, "nao_concluida", False, False)
    vs.gravar_eventos(con, vs.eventos_de([t], [], [], set(), [], faixa_ret(), 30), "v")
    payloads = [json.loads(p) for (p,) in con.execute("SELECT payload_json FROM eventos WHERE tipo = 'travessia'")]
    assert payloads[0]["status"] == "nao_concluida"


def test_origem_invalida_recusada(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO eventos (timestamp, origem, tipo) VALUES ('2026-11-12T10:00:00-03:00', 'camera', 'x')")


def test_timestamp_iso_sao_paulo(con):
    vs.gravar_eventos(con, _cenario()[:1], "v")
    ts = con.execute("SELECT timestamp FROM eventos").fetchone()[0]
    assert ts.endswith("-03:00")
    datetime.fromisoformat(ts)


def test_payload_com_numpy(con):
    ev = [vs.Evento("travessia", np.int64(3), np.int64(1), np.float32(1.5), {"x": np.int64(3), "y": np.float64(0.5)})]
    assert vs.gravar_eventos(con, ev, "v") == 1


def test_payload_marca_demonstracao(con):
    vs.gravar_eventos(con, _cenario(), "video_teste")
    for (p,) in con.execute("SELECT payload_json FROM eventos"):
        d = json.loads(p)
        assert d["demonstracao"] is True and d["video_id"] == "video_teste"
    assert con.execute("SELECT COUNT(*) FROM eventos WHERE origem != 'yolo'").fetchone()[0] == 0


def test_schema_igual_ao_banco_real(con, tmp_path):
    real = RAIZ / "data" / "processed" / "seguranca_viaria.db"
    if not real.exists():
        pytest.skip("banco real não gerado (rode os notebooks 03–06)")
    copia = tmp_path / "copia.db"
    shutil.copy(real, copia)                     # migra uma cópia: o teste não mexe no banco do projeto
    c2 = sqlite3.connect(copia)
    vs.migrar(c2)
    colunas = lambda c: [(r[1], r[2]) for r in c.execute("PRAGMA table_info(eventos)")]
    assert colunas(c2) == colunas(con)
    c2.close()


# ---------------------------------------------------------------- Tarefa 6: leitura de vídeo e detector
def test_video_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        vs.ler_video(tmp_path / "nao_existe.mp4")


def test_video_vazio(tmp_path):
    p = tmp_path / "vazio.mp4"
    p.write_bytes(b"")
    with pytest.raises(ValueError, match="vídeo"):
        vs.ler_video(p)


def test_video_corrompido(tmp_path):
    p = tmp_path / "lixo.mp4"
    p.write_bytes(np.random.default_rng(1).integers(0, 256, 5000, dtype=np.uint8).tobytes())
    with pytest.raises(ValueError, match="vídeo"):
        vs.ler_video(p)


def test_video_sintetico_e_gerador(tmp_path):
    import cv2
    p = tmp_path / "sint.mp4"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for i in range(10):
        w.write(np.full((48, 64, 3), i * 20, dtype=np.uint8))
    w.release()
    fps, largura, altura, quadros = vs.ler_video(p)
    assert (round(fps), largura, altura) == (10, 64, 48)
    assert inspect.isgenerator(quadros)
    assert sum(1 for _ in quadros) == 10


def test_quadro_sem_deteccao():
    img = ruido()
    assert vs.travessias([], faixa_ret(), 30) == []
    assert vs.conflitos([], faixa_ret(), 30) == [] and vs.bloqueios([], faixa_ret(), 30) == []
    assert np.array_equal(vs.borrar(img, []), img)


@pytest.mark.slow
def test_fumaca_modelo_real():
    videos = sorted(p for p in (RAIZ / "data" / "raw" / "video").iterdir() if p.suffix in {".mp4", ".ogv", ".webm"})
    if not videos:
        pytest.skip("sem vídeo em data/raw/video (Tarefa 7)")
    import detector
    classes = ["person", "car", "bus", "wheelchair"]
    vistos = []
    for i, (q, img, dets) in enumerate(detector.detectar(videos[0], classes, a_cada=1)):
        vistos += dets
        if i >= 29:
            break
    assert vistos and all(isinstance(d, vs.Deteccao) and d.classe in classes for d in vistos)


# ---------------------------------------------------------------- condutor de moto/bicicleta não é pedestre
def test_condutor_de_moto_nao_e_pedestre():
    piloto = D("person", (300, 10, 380, 150), 1)            # caixa da pessoa quase toda dentro da da moto
    moto = D("motorcycle", (280, 50, 420, 170), 9)
    pedestre = D("person", (100, 20, 160, 160), 2)         # ao lado, sem sobreposição
    ciclista, bike = D("person", (600, 0, 660, 140), 3), D("bicycle", (590, 60, 680, 160), 8)
    restantes = vs.sem_condutores([piloto, moto, pedestre, ciclista, bike])
    assert {d.track_id for d in restantes if d.classe == "person"} == {2}
    assert {d.classe for d in restantes} == {"person", "motorcycle", "bicycle"}   # veículos continuam


def test_condutor_nao_gera_conflito_com_a_propria_moto():
    dets = []
    for q in range(10):
        dy = 10 * q
        dets += [D("person", (30, 520 + dy, 70, 640 + dy), 1, q), D("motorcycle", (20, 560 + dy, 80, 660 + dy), 9, q)]
    assert vs.conflitos(vs.sem_condutores(dets), faixa_ret(), fps=30) == []


# ---------------------------------------------------------------- velocidade (escala da faixa)
def test_escala_da_faixa():
    # meio da borda A (50, 0) até o meio da borda B (50, 1200): 1200 px em 12 m
    assert faixa_ret().px_por_m() == pytest.approx(100.0)


def andando_rapido(px_por_quadro, quadros, track_id=7):
    return [vs.Deteccao(q, "car", (10, 300 + px_por_quadro * q, 90, 350 + px_por_quadro * q), 0.9, track_id) for q in quadros]


def test_velocidade_do_veiculo_no_conflito():
    dets = [vs.Deteccao(q, "person", (30, 500, 70, 600), 0.9, 1) for q in range(20)]
    dets += andando_rapido(10, list(range(20)))          # 10 px/quadro × 30 fps ÷ 100 px/m = 3 m/s = 10,8 km/h
    c = vs.conflitos(dets, faixa_ret(), fps=30)[0]
    assert c.velocidade_kmh == pytest.approx(10.8, abs=0.5)
    assert c.severidade == "normal"


def test_veiculo_rapido_tem_severidade_alta():
    dets = [vs.Deteccao(q, "person", (30, 500, 70, 600), 0.9, 1) for q in range(20)]
    dets += andando_rapido(30, list(range(20)))          # 30 px/quadro → 9 m/s = 32,4 km/h (≥ 30 km/h)
    c = vs.conflitos(dets, faixa_ret(), fps=30)[0]
    assert c.velocidade_kmh == pytest.approx(32.4, abs=1.0)
    assert c.severidade == "alta"


def test_travessia_rapida_demais_para_pedestre():
    rapida = vs.travessias(trajeto(1, atravessa(90)), faixa_ret(), fps=30)[0]    # 12 m em 3 s = 4 m/s
    normal = vs.travessias(trajeto(2, atravessa(300)), faixa_ret(), fps=30)[0]   # 1,2 m/s
    assert rapida.incompativel_pedestre is True and normal.incompativel_pedestre is False


# ---------------------------------------------------------------- rótulos e anotação visual
def test_rotulos_em_portugues():
    assert vs.rotulo(D("person", (0, 0, 10, 10), 1), na_faixa=True) == "Pedestre"
    assert vs.rotulo(D("person", (0, 0, 10, 10), 1), na_faixa=True, auxilio="wheelchair") == "Pedestre · cadeira de rodas"
    assert vs.rotulo(D("person", (0, 0, 10, 10), 1), na_faixa=True, auxilio="cane") == "Pedestre · bengala"
    assert vs.rotulo(D("person", (0, 0, 10, 10), 1), na_faixa=False) is None          # calçada: sem rótulo
    assert vs.rotulo(D("bus", (0, 0, 10, 10), 3), na_faixa=False) == "Ônibus"
    assert vs.rotulo(D("motorcycle", (0, 0, 10, 10), 4), na_faixa=True, conflito_kmh=25.4) == "Moto · 25 km/h"
    assert vs.rotulo(D("license plate", (0, 0, 10, 10)), na_faixa=False) is None


def test_auxilios_por_pessoa():
    assert vs.auxilios_por_pessoa(_com_auxilio(5)) == {1: "wheelchair"}
    assert vs.auxilios_por_pessoa(_com_auxilio(1)) == {}


def test_anotar_borra_antes_e_escreve_rotulo():
    img = ruido(400, 300)
    pessoa = D("person", (30, 150, 70, 300), 1)        # pés em (50, 300): dentro da faixa de teste
    f = faixa_de(RET, resolucao=(300, 400), lado_a=(0, 1), lado_b=(2, 3))
    copia = img.copy()
    out = vs.anotar(img, [pessoa], f)
    assert np.array_equal(img, copia)                                   # entrada intacta
    assert out.shape == img.shape
    assert borrada(img, out, (156, 183, 36, 64))                        # miolo da cabeça (sem a linha da caixa)
    assert not np.array_equal(out[120:148, 30:120], img[120:148, 30:120])   # rótulo escrito acima da caixa


def test_itens_condutor_nao_vira_pedestre_e_carro_longe_sem_rotulo():
    f = faixa_de(RET, resolucao=(1000, 1000), lado_a=(0, 1), lado_b=(2, 3))
    piloto = D("person", (20, 400, 80, 560), 1)                    # pés dentro da faixa, mas montado na moto
    moto = D("motorcycle", (10, 450, 95, 580), 9)
    pedestre = D("person", (30, 600, 70, 760), 2)
    carro_perto = D("car", (200, 500, 500, 700), 5)                # 200 px de altura = 20% da imagem
    carro_longe = D("car", (600, 100, 650, 130), 6)                # 30 px = 3%: estacionado ao fundo
    itens = {(i.texto, i.track_id) for i in vs.itens_anotacao([piloto, moto, pedestre, carro_perto, carro_longe], f)}
    assert ("Pedestre", 2) in itens
    assert not any(t == "Pedestre" and tid == 1 for t, tid in itens)       # piloto não é pedestre
    assert ("Moto", 9) in itens and ("Carro", 5) in itens
    assert (None, 6) in itens                                               # caixa fina, sem rótulo


def test_borrao_anonimiza_pessoa_grande_em_close():
    """Com bloco fixo de 10 px, um rosto de 300 px continuava reconhecível; o bloco precisa crescer com a pessoa:
    no máximo vs.BLOCOS_MAX blocos na largura da caixa, qualquer que seja o tamanho."""
    rng = np.random.default_rng(0)
    img = rng.integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
    pessoa = vs.Deteccao(0, "person", (600, 0, 1200, 1080), 0.9, 1)          # 600 px de largura, em close
    out = vs.borrar(img, [pessoa])
    linha = out[100, 600:1200]                                                # dentro da região da cabeça
    trocas = int((np.abs(np.diff(linha.astype(int), axis=0)).sum(axis=1) > 0).sum())
    assert trocas + 1 <= vs.BLOCOS_MAX


def test_borrao_pessoa_pequena_continua_com_blocos_de_10():
    img = np.random.default_rng(1).integers(0, 256, (400, 400, 3), dtype=np.uint8)
    pessoa = vs.Deteccao(0, "person", (100, 100, 140, 260), 0.9, 1)          # 40 px de largura, longe
    out = vs.borrar(img, [pessoa])
    linha = out[110, 100:140]
    trocas = int((np.abs(np.diff(linha.astype(int), axis=0)).sum(axis=1) > 0).sum())
    assert trocas + 1 <= 4 and not np.array_equal(out[110, 100:140], img[110, 100:140])


def test_rosto_detectado_e_borrado_inteiro():
    """Em close, a cabeça nem sempre está no quarto de cima da caixa da pessoa (sentada, cortada pela borda):
    uma detecção 'face' é borrada inteira, como a placa."""
    img = np.random.default_rng(2).integers(0, 256, (600, 600, 3), dtype=np.uint8)
    rosto = vs.Deteccao(0, "face", (200, 400, 320, 540), 0.5, None)
    out = vs.borrar(img, [rosto])
    assert not np.array_equal(out[400:540, 200:320], img[400:540, 200:320])
    assert np.array_equal(out[:390], img[:390])


def _pontos(vis):
    """17 pontos COCO; `vis` = {índice: (x, y)} com confiança 0.9, o resto com 0."""
    xy, cf = np.zeros((17, 2)), np.zeros(17)
    for i, p in vis.items():
        xy[i], cf[i] = p, 0.9
    return xy, cf


def test_rosto_pela_pose_cobre_os_pontos_com_folga():
    xy, cf = _pontos({0: (500, 300), 1: (490, 290), 2: (510, 290), 3: (475, 295), 4: (525, 295)})
    (r,) = vs.rostos_pela_pose([xy], [cf], [(400, 250, 600, 800)], quadro=7)
    x1, y1, x2, y2 = r.caixa
    assert r.classe == "face" and r.quadro == 7
    assert x1 < 475 and x2 > 525 and y1 < 290 and y2 > 300
    assert (x2 - x1) >= 0.12 * 550            # tamanho mínimo proporcional à pessoa (perfil com pontos colados)


def test_rosto_pela_pose_ignora_pontos_incertos_e_corpo():
    xy, cf = _pontos({0: (500, 300), 5: (450, 400), 6: (550, 400)})   # só o nariz é do rosto: não basta
    assert vs.rostos_pela_pose([xy], [cf], [(400, 250, 600, 800)], quadro=0) == []
    xy2, cf2 = _pontos({1: (490, 290), 2: (510, 290)})
    cf2[1] = 0.1                                                        # olho esquerdo incerto
    assert vs.rostos_pela_pose([xy2], [cf2], [(400, 250, 600, 800)], quadro=0) == []
