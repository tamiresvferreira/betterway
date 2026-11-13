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
