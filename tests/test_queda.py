"""Regra de suspeita de acidente (protótipo): pessoa deitada, parada, na faixa ou na pista por >= 3 s."""
import visao as v

FPS = 10
# faixa: 100..900 × 400..500 px, 8 m de comprimento → 100 px/m; pista: 0..1000 × 300..600
FAIXA = v.Faixa([(100, 400), (900, 400), (900, 500), (100, 500)], (1000, 800), (3, 0), (1, 2), 8.0)
PISTA = [(0, 300), (1000, 300), (1000, 600), (0, 600)]


def _pessoa(quadros, caixa, tid=1, dx_por_quadro=0.0):
    x1, y1, x2, y2 = caixa
    return [v.Deteccao(q, "person", (x1 + q * dx_por_quadro, y1, x2 + q * dx_por_quadro, y2), 0.8, tid)
            for q in quadros]


DEITADA_NA_FAIXA = (400, 440, 520, 480)      # 120 × 40: largura 3 × altura, pés em y = 480 (na faixa)


def test_deitada_parada_na_faixa_por_3s_dispara_uma_vez():
    s = v.suspeitas_de_queda(_pessoa(range(0, 50), DEITADA_NA_FAIXA), FAIXA, FPS)
    assert len(s) == 1 and s[0].track_id == 1 and s[0].quadro_inicio == 0 and s[0].quadro == 30


def test_deitada_na_pista_fora_da_faixa_dispara_so_com_a_pista():
    na_pista = (400, 540, 520, 580)          # pés em y = 580: pista, não faixa
    dets = _pessoa(range(0, 50), na_pista)
    assert v.suspeitas_de_queda(dets, FAIXA, FPS) == []
    assert len(v.suspeitas_de_queda(dets, FAIXA, FPS, pista=PISTA)) == 1


def test_deitada_por_menos_de_3s_nao_dispara():
    assert v.suspeitas_de_queda(_pessoa(range(0, 25), DEITADA_NA_FAIXA), FAIXA, FPS) == []


def test_de_pe_parada_na_faixa_nao_dispara():
    assert v.suspeitas_de_queda(_pessoa(range(0, 60), (450, 330, 490, 480)), FAIXA, FPS) == []


def test_sentada_no_meio_fio_fora_da_pista_nao_dispara():
    sentada = (450, 620, 520, 680)           # 70 × 60 e fora da pista
    assert v.suspeitas_de_queda(_pessoa(range(0, 60), sentada), FAIXA, FPS, pista=PISTA) == []


def test_deitada_se_movendo_nao_dispara():
    # 1 m/s = 100 px/s = 10 px por quadro: alguém se arrastando ou caixa de outra coisa
    assert v.suspeitas_de_queda(_pessoa(range(0, 50), DEITADA_NA_FAIXA, dx_por_quadro=10), FAIXA, FPS) == []


def test_interrupcao_longa_recomeca_a_contagem():
    dets = _pessoa(range(0, 20), DEITADA_NA_FAIXA) + _pessoa(range(40, 60), DEITADA_NA_FAIXA)
    assert v.suspeitas_de_queda(dets, FAIXA, FPS) == []


def test_evento_de_suspeita_entra_nos_eventos():
    s = v.suspeitas_de_queda(_pessoa(range(0, 50), DEITADA_NA_FAIXA), FAIXA, FPS)
    ev = v.eventos_de([], [], [], set(), [], FAIXA, FPS, suspeitas_=s)
    assert [(e.tipo, e.quadro, e.track_id) for e in ev] == [("suspeita_acidente", 30, 1)]
    assert ev[0].valor == 3.0
