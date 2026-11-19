"""Componentes visuais da plataforma (src/operador/componentes.py): cada um fala por palavra, não só por cor."""
import componentes as cp


def test_semaforo_acende_a_luz_certa_e_escreve_o_estado():
    h = cp.semaforo_svg("pedestre_verde")
    assert 'data-carros="vermelho"' in h and 'data-pedestre="verde"' in h
    assert "Carros: vermelho" in h and "Pedestre: verde" in h
    assert 'data-carros="amarelo"' in cp.semaforo_svg("carros_amarelo")
    assert "pisca" in cp.semaforo_svg("pedestre_pisca")
    assert "Sem sinal do nó" in cp.semaforo_svg(None)


def test_feed_traduz_os_eventos_do_no():
    h = cp.feed_eventos([{"tipo": "pedido_recusado_ambulancia", "recebido_em": "2026-11-18T17:40:02-03:00"},
                         {"tipo": "modo_alterado", "detalhe": {"modo": "chuva"}, "recebido_em": "2026-11-18T17:39:00-03:00"},
                         {"tipo": "desconhecido", "recebido_em": "2026-11-18T17:38:00-03:00"}])
    assert "Pedido adiado: ambulância chegando" in h and "17:40" in h
    assert "Modo mudou para Chuva" in h and "desconhecido" in h
    assert "Nenhum evento" in cp.feed_eventos([])


def test_quadro_poe_cada_ocorrencia_na_sua_etapa_com_os_tempos():
    linhas = [{"id": 1, "tipo": "Suspeita de acidente", "origem": "visao", "estado": "pendente", "aberta": "17:40",
               "confirmar": None, "despachar": None, "atender": None, "motivo": None},
              {"id": 2, "tipo": "Ocorrência reportada", "origem": "operador", "estado": "encerrada", "aberta": "16:00",
               "confirmar": 43, "despachar": 37, "atender": 600, "motivo": None},
              {"id": 3, "tipo": "Suspeita de acidente", "origem": "visao", "estado": "descartada", "aberta": "15:00",
               "confirmar": None, "despachar": None, "atender": None, "motivo": "pessoa se levantou"}]
    h = cp.quadro_ocorrencias(linhas)
    for etapa in ("Aguardando o Trânsito", "Aguardando a Saúde", "Atendimento a caminho", "Concluídas"):
        assert etapa in h
    assert h.index("Nº 1") < h.index("Aguardando a Saúde") < h.index("Nº 2")
    assert "43 s" in h and "10 min" in h and "pessoa se levantou" in h


def test_ranking_destaca_o_piloto():
    h = cp.ranking_pontos([{"rank_urbano": 1, "via": "Avenida do Imperador", "atropelamentos": 14, "piloto": False},
                          {"rank_urbano": 26, "via": "Largo da Concórdia", "atropelamentos": 22, "piloto": True}])
    assert "Avenida do Imperador" in h and "piloto" in h and "1º" in h


def test_cartoes_dos_clipes_mostram_esperado_e_obtido():
    h = cp.cartoes_clipes([{"clipe": "cadeirante_01", "auxilio_esperado": "wheelchair", "auxilio_obtido": "wheelchair",
                            "acerto": True},
                           {"clipe": "muleta_01", "auxilio_esperado": "crutch", "auxilio_obtido": "nenhum",
                            "acerto": False}])
    assert "cadeira de rodas" in h and "muleta" in h and "Acertou" in h and "Errou" in h
