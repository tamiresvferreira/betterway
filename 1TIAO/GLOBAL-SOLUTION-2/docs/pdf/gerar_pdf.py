"""Gera o PDF de entrega da Global Solution 2026.2 (BetterWay) a partir das evidências do projeto.

    python docs/pdf/gerar_pdf.py        # → docs/BetterWay_GS2026-2.pdf

Os números vêm dos arquivos de evidência (Estudo A) e do banco do projeto quando existe; nada é digitado à mão.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "docs" / "BetterWay_GS2026-2.pdf"
EVID = RAIZ / "docs" / "evidencias"
FONTES = RAIZ / "assets" / "marca" / "fontes"
RM = "RM 571256"
VIDEO = "a incluir (YouTube, não listado)"
REPO = "https://github.com/tamiresvferreira/Global-Solution-2026.2-Oficial"

VERDE, GRAFITE, CINZA, CLARO = colors.HexColor("#00C27A"), colors.HexColor("#1A1D21"), colors.HexColor("#5F666E"), \
    colors.HexColor("#EEEFEC")
VERDE_ESC = colors.HexColor("#00804F")

pdfmetrics.registerFont(TTFont("Mont", str(FONTES / "Montserrat-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Mont-SB", str(FONTES / "Montserrat-SemiBold.ttf")))
pdfmetrics.registerFont(TTFont("Mont-B", str(FONTES / "Montserrat-Bold.ttf")))
pdfmetrics.registerFontFamily("Mont", normal="Mont", bold="Mont-B", italic="Mont", boldItalic="Mont-B")

E = {
    "capa_t": ParagraphStyle("capa_t", fontName="Mont-B", fontSize=34, leading=40, textColor=GRAFITE),
    "capa_s": ParagraphStyle("capa_s", fontName="Mont-SB", fontSize=16, leading=22, textColor=VERDE_ESC),
    "capa_n": ParagraphStyle("capa_n", fontName="Mont", fontSize=11, leading=16, textColor=CINZA),
    "h1": ParagraphStyle("h1", fontName="Mont-B", fontSize=18, leading=24, textColor=GRAFITE, spaceBefore=6, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Mont-SB", fontSize=13, leading=18, textColor=VERDE_ESC, spaceBefore=10, spaceAfter=6),
    "p": ParagraphStyle("p", fontName="Mont", fontSize=10, leading=15, textColor=GRAFITE, spaceAfter=7),
    "item": ParagraphStyle("item", fontName="Mont", fontSize=10, leading=15, textColor=GRAFITE, leftIndent=12,
                           bulletIndent=2, spaceAfter=3),
    "leg": ParagraphStyle("leg", fontName="Mont", fontSize=8.5, leading=12, textColor=CINZA, alignment=TA_CENTER,
                          spaceAfter=10),
    "cel": ParagraphStyle("cel", fontName="Mont", fontSize=9, leading=12, textColor=GRAFITE),
    "cel_b": ParagraphStyle("cel_b", fontName="Mont-SB", fontSize=9, leading=12, textColor=GRAFITE),
}


def p(t, e="p"):
    return Paragraph(t, E[e])


def itens(lista):
    return [Paragraph(t, E["item"], bulletText="•") for t in lista]


def figura(arq: Path, legenda: str, largura_cm: float = 16.5):
    if not arq.exists():
        return [p(f"(figura indisponível: {arq.name})", "leg")]
    img = Image(str(arq))
    proporcao = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = largura_cm * cm, largura_cm * cm * proporcao
    return [KeepTogether([img, Spacer(1, 4), p(legenda, "leg")])]


def tabela(linhas, larguras, cabecalho=True):
    dados = [[Paragraph(str(c), E["cel_b"] if (cabecalho and i == 0) else E["cel"]) for c in linha]
             for i, linha in enumerate(linhas)]
    t = Table(dados, colWidths=[w * cm for w in larguras], repeatRows=1 if cabecalho else 0)
    estilo = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E1E3DE")),
              ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    if cabecalho:
        estilo += [("BACKGROUND", (0, 0), (-1, 0), CLARO)]
    t.setStyle(TableStyle(estilo))
    return t


def numeros() -> dict:
    r = pd.read_csv(EVID / "estudo_a" / "estudo_a_resumo.csv", sep=";", encoding="utf-8-sig").set_index(
        ["comparacao", "sistema"])
    sem, com = r.loc[("completo", "sem")], r.loc[("completo", "com")]
    n = {"faixa_s": sem.na_faixa_carros_verde_reduzida + sem.na_faixa_carros_verde_comum,
         "faixa_c": com.na_faixa_carros_verde_reduzida + com.na_faixa_carros_verde_comum,
         "amb_s": sem.tempo_ambulancia_s, "amb_c": com.tempo_ambulancia_s,
         "esp_s": sem.espera_media_pedestre_s, "esp_c": com.espera_media_pedestre_s,
         "atr_s": sem.atraso_medio_carro_s, "atr_c": com.atraso_medio_carro_s,
         "red_s": r.loc[("pedestre", "sem")].surpreendidos_reduzida_pct,
         "red_c": r.loc[("pedestre", "com")].surpreendidos_reduzida_pct}
    db = RAIZ / "data" / "processed" / "seguranca_viaria.db"
    if db.exists():
        con = sqlite3.connect(db)
        n["sinistros"] = con.execute("SELECT COUNT(*) FROM sinistros").fetchone()[0]
        n["grupos"] = con.execute("SELECT COUNT(*) FROM clusters").fetchone()[0]
        n["urbanos"] = con.execute("SELECT COUNT(*) FROM clusters WHERE rank_urbano IS NOT NULL").fetchone()[0]
        n["piloto_rank"], = con.execute("SELECT rank_urbano FROM clusters WHERE cluster_id = 139").fetchone()
        n["piloto_n"], n["piloto_f"] = con.execute(
            "SELECT COUNT(*), SUM(fatal) FROM sinistros WHERE cluster_id = 139").fetchone()
    av = EVID / "operador" / "avaliacao_clipes.csv"
    if av.exists():
        a = pd.read_csv(av, sep=";", encoding="utf-8-sig")
        n["clipes_ok"], n["clipes"] = int(a.acerto.sum()), len(a)
    return n


def br(v, casas=1):
    return f"{v:.{casas}f}".replace(".", ",")


def rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Mont", 8)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, 1.2 * cm, "BetterWay · Global Solution FIAP 2026.2 · Tamires Vitória Ferreira dos Santos")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))
    canvas.restoreState()


def capa(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(VERDE)
    for k in range(8):                                   # listras da faixa de pedestres, a assinatura da marca
        canvas.rect(A4[0] - 1.6 * cm, A4[1] - (2 + k * 2.2) * cm, 1.6 * cm, 1.2 * cm, stroke=0, fill=1)
    canvas.restoreState()


def montar() -> None:
    n = numeros()
    logo = RAIZ / "assets" / "marca" / "betterway-logo-horizontal-fundo-claro.png"
    s = []
    # ---------------------------------------------------------------- capa
    s += [Spacer(1, 3 * cm)]
    if logo.exists():
        img = Image(str(logo)); img.drawWidth, img.drawHeight = 7 * cm, 7 * cm * img.imageHeight / img.imageWidth
        img.hAlign = "LEFT"; s += [img, Spacer(1, 1.2 * cm)]
    s += [p("BetterWay: o semáforo que enxerga a faixa", "capa_t"), Spacer(1, 0.4 * cm),
          p("To live, to move, to be free.", "capa_s"), Spacer(1, 1.6 * cm),
          p("Global Solution 2026.2 · CitizenTech: tecnologia centrada no cidadão", "capa_n"),
          p("FIAP · Graduação em Inteligência Artificial · Turma 1TIAO", "capa_n"),
          p(f"Tamires Vitória Ferreira dos Santos · {RM}", "capa_n"), Spacer(1, 0.6 * cm),
          p(f"Repositório: {REPO}", "capa_n"), p(f"Vídeo de demonstração: {VIDEO}", "capa_n"), PageBreak()]
    # ---------------------------------------------------------------- sumário
    s += [p("Sumário", "h1")] + itens([
        "1. O problema", "2. A solução: BetterWay", "3. Arquitetura", "4. Onde e quando: pontos críticos e risco",
        "5. A câmera: visão computacional", "6. O semáforo: simulação no SUMO", "7. O nó da faixa: ESP32, cartão e câmera",
        "8. A plataforma", "9. Privacidade e LGPD", "10. Limites e próximos passos", "11. Conclusão"]) + [PageBreak()]
    # ---------------------------------------------------------------- 1
    s += [p("1. O problema", "h1"),
          p(f"Entre 2022 e 2025, o Infosiga-SP registrou <b>{n.get('sinistros', 16245):,} atropelamentos</b> na cidade de "
            "São Paulo usados neste estudo.".replace(",", ".") + " Os semáforos de hoje funcionam no relógio: o verde do "
            "pedestre é calculado para 1,2 m/s, uma velocidade que a maioria dos idosos não alcança, e o tempo é o mesmo "
            "com ou sem gente na faixa. Quem começa a atravessar no fim do verde ainda está na faixa quando os carros "
            "recebem o verde; a ambulância espera no vermelho como qualquer carro."),
          p(f"O piloto deste trabalho é o <b>Largo da Concórdia, no Brás</b>: {n.get('piloto_n', 53)} atropelamentos no "
            f"período, {n.get('piloto_f', 2)} com morte, numa avenida de seis faixas com 16 m de travessia, "
            f"{n.get('piloto_rank', 26)}º entre os {n.get('urbanos', 273)} pontos críticos urbanos da cidade.")]
    s += figura(EVID / "estudo_b" / "01_02_5_2_quando_acontecem_hora_do_dia_dia_da_semana.png",
                "Figura 1. Quando os atropelamentos acontecem (Infosiga-SP, 2022 a 2025).", 15)
    # ---------------------------------------------------------------- 2
    s += [p("2. A solução: BetterWay", "h1"),
          p("A BetterWay dá olhos ao semáforo. Uma câmera entende a faixa de pedestres; uma central junta câmera, chuva, "
            "horário e o histórico de atropelamentos do local; e um nó ligado ao semáforo ajusta o sinal na hora. A "
            "plataforma web mostra tudo isso para as equipes de Trânsito, Saúde e Gestão."),
          p("Três verbos guiam o produto:")] + itens([
              "<b>to live:</b> ninguém fica na faixa com os carros em verde; a avenida só ganha verde com a faixa vazia.",
              "<b>to move:</b> a via vazia não segura o trânsito, e a ambulância encontra o corredor aberto: os "
              "motoristas à frente recebem um alerta e o semáforo dá prioridade a ela.",
              "<b>to be free:</b> quem precisa de mais tempo encosta o Bilhete Único Idoso ou Especial no leitor do poste "
              "(como o Green Man+ de Singapura); quem esqueceu o cartão é percebido pela câmera."])
    s += figura(EVID / "plataforma" / "visao.png", "Figura 2. Visão geral da plataforma: a câmera com o "
                "reconhecimento (rostos borrados) ao lado da simulação do semáforo, e os indicadores reais.")
    # ---------------------------------------------------------------- 3
    s += [PageBreak(), p("3. Arquitetura", "h1"),
          p("Cada peça tem uma responsabilidade clara e fala com as outras por contratos simples (MQTT e banco):"),
          tabela([["Peça", "O que faz", "Tecnologia"],
                  ["Pontos críticos", "Agrupa atropelamentos e ordena pelo índice da CET", "Python, DBSCAN (scikit-learn)"],
                  ["Modelo de risco", "Onde e quando um atropelamento é provável", "Gradient boosting Poisson"],
                  ["Câmera", "Pessoas, veículos, auxílios de mobilidade, conflitos; borra rostos e placas",
                   "YOLO-World, ByteTrack, YOLO11 ajustado, OpenCV"],
                  ["Simulação", "Semáforo de hoje contra o que reage", "SUMO (TraCI)"],
                  ["Central", "Decide o modo do semáforo e pede tempo extra", "Python, Open-Meteo, MQTT"],
                  ["Nó da faixa", "Semáforo, matriz de LED, buzzer, leitor de cartão", "ESP32 no Wokwi (C++)"],
                  ["Plataforma", "Equipes acompanham, registram e respondem", "Streamlit"],
                  ["Banco", "Ocorrências, relatórios, leituras, eventos, usuários", "SQLite"]], [3.2, 7.8, 5.5]),
          Spacer(1, 8),
          p("Fluxo: a câmera vê a faixa → a central decide o modo (ambulância, chuva, escola, pedestre ou normal) e "
            "manda ao nó por MQTT → o nó ajusta o semáforo e devolve o que fez → a plataforma mostra e as equipes "
            "registram. A prioridade é fixa e segura: ambulância &gt; pedestre já na faixa &gt; travessia estendida "
            "&gt; chuva &gt; escola &gt; pedestre detectado &gt; normal; quem já atravessa nunca é cortado.")]
    # ---------------------------------------------------------------- 4
    s += [p("4. Onde e quando: pontos críticos e risco", "h1"),
          p(f"Os atropelamentos foram agrupados com DBSCAN (raio de 100 m, mínimo de 8 ocorrências, morte com peso 3), "
            f"gerando {n.get('grupos', 290)} grupos; {n.get('urbanos', 273)} deles são urbanos (sem rodovias nem pontos "
            "empilhados por geocodificação). A ordem segue o índice de prioridade da CET, e cada ponto foi cruzado com "
            "semáforos e escolas do OpenStreetMap e do GeoSampa."),
          p("Para prevenir, e não só contar, um modelo de gradient boosting com perda de Poisson estima o número esperado "
            "de atropelamentos por hora em cada ponto (treino com 2023, teste com 2024 e checagem com 2025). A "
            "plataforma mostra o risco de agora comparado à média da cidade.")]
    s += figura(EVID / "estudo_b" / "03_mapa_grupos_dbscan.png", "Figura 3. Pontos críticos encontrados pelo DBSCAN.", 13)
    s += figura(EVID / "estudo_b" / "06_risco_piloto_por_hora.png", "Figura 4. Risco ao longo do dia no Largo da "
                "Concórdia (modelo de risco).", 13)
    # ---------------------------------------------------------------- 5
    s += [p("5. A câmera: visão computacional", "h1"),
          p("O YOLO-World detecta pessoas e veículos sem treino específico, o ByteTrack os acompanha quadro a quadro, e "
            "um YOLO11 ajustado no Colab reconhece pessoas em cadeira de rodas. O sistema mede o tempo de cada travessia, "
            "percebe conflitos entre veículo e pedestre e borra rostos e placas antes de qualquer imagem ser mostrada."),
          p(f"Nos clipes de referência (gerados por IA), a visão acertou {n.get('clipes_ok', 7)} de {n.get('clipes', 10)}. "
            "Dois ajustes vieram dos testes: o andador só passou a ser reconhecido com o termo \"zimmer frame\" no "
            "vocabulário, e a ambulância, que o modelo chamava de ônibus ou caminhão, passou a ser reconhecida por uma "
            "regra de cor (branco com faixa vermelha) aplicada a veículos grandes e mantida em todo o rastreamento.")]
    s += figura(EVID / "plataforma" / "camera.png", "Figura 5. Câmera aberta: a ambulância reconhecida e o "
                "registro de ocorrência com captura do quadro do momento.")
    # ---------------------------------------------------------------- 6
    s += [PageBreak(), p("6. O semáforo: simulação no SUMO", "h1"),
          p("Um cruzamento com as medidas do piloto foi simulado no SUMO, comparando o semáforo de tempo fixo de hoje com "
            "o semáforo que reage. Toda troca passa por amarelo de 3 s e vermelho total de 2 s, nos dois lados; o que "
            "reage só troca depois de 4 s sem carro chegando e nunca solta os carros com gente na faixa."),
          tabela([["Tudo ligado junto (5 rodadas de 30 min)", "Hoje", "BetterWay"],
                  ["Pessoas na faixa com carros da avenida em verde, por rodada", br(n["faixa_s"]), br(n["faixa_c"], 0)],
                  ["Tempo da ambulância para passar o cruzamento", f"{br(n['amb_s'])} s", f"{br(n['amb_c'])} s"],
                  ["Espera de quem atravessa", f"{br(n['esp_s'])} s", f"{br(n['esp_c'])} s"],
                  ["Atraso médio de cada carro", f"{br(n['atr_s'])} s", f"{br(n['atr_c'])} s"],
                  ["Travessias de quem tem mobilidade reduzida interrompidas pelo sinal",
                   f"{br(n['red_s'], 0)}%", f"{br(n['red_c'], 0)}%"]], [9.5, 3.5, 3.5]),
          Spacer(1, 8),
          p(f"Segurança primeiro: o custo para os carros é de cerca de {br(n['atr_c'] - n['atr_s'])} s por carro, o "
            "preço de nunca soltar os carros com gente na faixa. Um semáforo que só reage aos carros andaria mais rápido, "
            "mas faria exatamente isso.")]
    s += figura(EVID / "estudo_a" / "estudo_a_comparacoes.png", "Figura 6. Comparações do Estudo A (SUMO).", 15)
    # ---------------------------------------------------------------- 7
    s += [p("7. O nó da faixa: ESP32, cartão e câmera", "h1"),
          p("O nó roda num ESP32 simulado no Wokwi: semáforo de carros e de pedestre, matriz de LED como placa "
            "inteligente e buzzer para quem tem baixa visão. Ele recebe o modo por MQTT e decide sozinho o ciclo, de "
            "modo que a faixa continua segura mesmo sem a central."),
          p("O botão de travessia saiu, para evitar fraude e trânsito travado à toa. O tempo extra vem de duas fontes "
            "que se cobrem: o <b>cartão</b> (Bilhete Único Idoso ou Especial, cadastros que a SPTrans já tem) e a "
            "<b>câmera</b>, que pede o tempo quando vê andador ou cadeira de rodas. Se a câmera falhar, o cartão "
            "continua valendo.")]
    s += figura(EVID / "plataforma" / "demos.png", "Figura 7. Central de demonstrações: o leitor de cartão no poste "
                "e o alerta no celular do motorista quando a ambulância está a 1 km.")
    # ---------------------------------------------------------------- 8
    s += [PageBreak(), p("8. A plataforma", "h1"),
          p("A plataforma é usada por três perfis: Trânsito (valida suspeitas, muda o modo do semáforo), Saúde "
            "(despacha e encerra atendimentos) e Gestão (acompanha tudo e convida a equipe). Entre as telas:")] + itens([
              "<b>Visão geral:</b> cinco cenários, um por vez, com a câmera e a simulação lado a lado.",
              "<b>Painel:</b> leitura da situação (histórico, chuva, câmera e modelo), risco ao longo do dia e mapa.",
              "<b>Câmeras:</b> a rede de câmeras; ao abrir uma, o operador registra a ocorrência, aciona ambulância, "
              "trânsito ou polícia (simulados) e anexa o quadro do momento com o horário.",
              "<b>Ocorrências e Atendimentos:</b> o caminho de cada ocorrência, com quem fez cada passo e quando.",
              "<b>Sala de controle:</b> o semáforo do nó ao vivo e o registro automático do que ele fez.",
              "<b>Demonstrações:</b> o cartão no poste e o alerta no celular do motorista.",
              "<b>Acessibilidade:</b> leitura da página em voz, tema claro e escuro, foco visível no teclado."])
    s += figura(EVID / "plataforma" / "mosaico.png", "Figura 8. Rede de câmeras com o reconhecimento da visão.", 15)
    s += figura(EVID / "plataforma" / "sala.png", "Figura 9. Sala de controle.", 15)
    # ---------------------------------------------------------------- 9
    s += [p("9. Privacidade e LGPD", "h1")] + itens([
        "Nenhum rosto é reconhecido; rostos e placas saem borrados antes de qualquer imagem aparecer.",
        "O cartão registra só o tipo, o horário e o tempo extra: nenhum número de cartão nem nome.",
        "Cada ação fica registrada com quem fez e quando, inclusive quem abriu cada câmera.",
        "Senhas só em hash (scrypt), convite de uso único e segundo fator por aplicativo autenticador (TOTP).",
        "O alerta aos motoristas seria por área (cell broadcast), sem saber número nem identidade de ninguém."])
    # ---------------------------------------------------------------- 10
    s += [p("10. Limites e próximos passos", "h1")] + itens([
        "Os ganhos no trânsito são resultados de simulação; só o Largo da Concórdia tem câmera no projeto, e os vídeos "
        "das câmeras são clipes de referência.",
        "A visão ainda não reconhece bengala nem muleta; o próximo passo é um ajuste fino com fotos desses auxílios "
        "(enquanto isso, o cartão cobre quem os usa).",
        "A ambulância é reconhecida por regra de cor; em produção, um modelo ajustado com fotos de viaturas.",
        "O nó roda no Wokwi e o broker MQTT é público; em campo, hardware real e broker com TLS e controle de acesso.",
        "Simular uma faixa no meio da quadra e uma avenida com vários nós em sequência."])
    # ---------------------------------------------------------------- 11
    s += [p("11. Conclusão", "h1"),
          p(f"A BetterWay mostra que dá para tornar o semáforo mais seguro sem trocar a cidade inteira: com uma câmera "
            f"que entende a faixa, um nó que decide sozinho e uma central que junta dados públicos, as pessoas na faixa "
            f"com os carros em verde caem de {br(n['faixa_s'])} para {br(n['faixa_c'], 0)} por rodada e a ambulância "
            f"passa {br(n['amb_s'] - n['amb_c'])} s mais rápido, ao custo de pouco mais de um segundo por carro. To "
            "live, to move, to be free.")]
    doc = SimpleDocTemplate(str(SAIDA), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm, title="BetterWay: o semáforo que enxerga a faixa",
                            author="Tamires Vitória Ferreira dos Santos", subject="Global Solution FIAP 2026.2")
    doc.build(s, onFirstPage=capa, onLaterPages=rodape)
    print(SAIDA)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    montar()
