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
