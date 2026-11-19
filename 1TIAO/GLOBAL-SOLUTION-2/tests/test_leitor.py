"""Botão de leitura em voz: usa a voz do navegador em pt-BR, lê os textos da página e não chama serviço externo."""
import leitor


def test_botao_le_em_portugues_com_a_voz_do_navegador():
    h = leitor.html_botao()
    assert "speechSynthesis" in h and 'u.lang = "pt-BR"' in h and "Ouvir esta página" in h
    assert "__SELETORES__" not in h and "h1, h2, h3" in h
    assert "fetch(" not in h and "XMLHttpRequest" not in h          # nada sai do navegador
    assert 'aria-pressed="false"' in h                               # estado anunciado a leitores de tela
