"""Os quatro cenários da Visão geral: cada um é um take de vídeo (Veo 3) ao lado da simulação Hoje × BetterWay.

A ordem segue os pilares (to live, to move, to be free). A seta passa ao próximo e, depois do último, volta ao
primeiro. O vídeo de cada cenário é procurado em assets/cameras como `visao_geral_<id>.mp4`; sem ele, a página mostra um espaço reservado.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PASTA_VIDEOS = Path(__file__).resolve().parents[2] / "assets" / "cameras"
PASTA_ANOTADOS = Path(__file__).resolve().parents[2] / "data" / "processed" / "veo3"
CLIPE_DO_CENARIO = {"conflito": "bengala_01", "transito": "normal_02", "ambulancia": "ambulancia_01",
                    "pedestre": "cadeirante_03", "andador": "andador_01"}


@dataclass(frozen=True)
class Cenario:
    id: str
    verbo: str
    icone: str
    titulo: str
    texto: str
    cena: str            # nome da cena exportada da simulação (cruzamento.carregar)

    @property
    def arquivo_video(self) -> str:
        return f"visao_geral_{self.id}.mp4"

    @property
    def clipe_anotado(self) -> str:
        """O mesmo vídeo depois da visão computacional (caixas, rótulos e borrões), como nas câmeras."""
        return CLIPE_DO_CENARIO.get(self.id, "")


CENARIOS: tuple[Cenario, ...] = (
    Cenario("conflito", "to live", "vida", "Ninguém fica na faixa com os carros em verde",
            "Quem começa a atravessar no fim do verde ainda está na faixa quando os carros recebem o verde. A "
            "BetterWay vê a pessoa e só libera a avenida com a faixa vazia.", "conflito"),
    Cenario("transito", "to move", "rota", "Faz o trânsito andar",
            "Quando a rua de lado fica 4 segundos sem nenhum carro chegando, o verde volta para a avenida, sempre com "
            "amarelo e vermelho total antes da troca. Se um carro chega nesse meio-tempo, a preferência continua com "
            "ele.", "transito"),
    Cenario("ambulancia", "to move", "rota", "Abre caminho para a ambulância",
            "Os motoristas à frente recebem um alerta e abrem espaço antes de ela chegar. O semáforo dá prioridade "
            "a ela com a faixa vazia, e ela passa direto.", "ambulancia"),
    Cenario("pedestre", "to be free", "pedestre", "Dá tempo a quem precisa atravessar",
            "Quem tem o Bilhete Único Idoso ou Especial encosta o cartão no poste da faixa e ganha mais tempo para "
            "atravessar, como no Green Man+ de Singapura. Sem botão para apertar, sem fraude.", "pedestre"),
    Cenario("andador", "to be free", "camera", "A câmera percebe quem esqueceu o cartão",
            "Ela reconhece andador, muleta ou cadeira de rodas e pede o tempo extra sozinha. Se a câmera falhar, o "
            "cartão continua valendo: um cobre o outro.", "pedestre"),
)


def proximo(i: int) -> int:
    return (i + 1) % len(CENARIOS)


def anterior(i: int) -> int:
    return (i - 1) % len(CENARIOS)


def video_do_cenario(c: Cenario, pasta: Path = PASTA_VIDEOS, anotados: Path | None = None) -> Path | None:
    """Prefere o vídeo anotado pela visão (mostra o reconhecimento); sem ele, o vídeo original do cenário."""
    if anotados is not None and c.clipe_anotado:
        a = Path(anotados) / f"{c.clipe_anotado}_anotado.mp4"
        if a.is_file():
            return a
    f = Path(pasta) / c.arquivo_video
    return f if f.is_file() else None
