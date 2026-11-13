"""Visão computacional na faixa de pedestres (Estudo B, Via Segura SP).

Funções puras e testáveis: geometria da faixa, travessias, conflitos, PCD, borrão (LGPD), eventos no banco e leitura
de vídeo. O detector (YOLO-World + ByteTrack) fica isolado em detector.py; tudo aqui recebe listas de Deteccao, o que
permite testar com caixas escritas à mão, sem GPU e sem baixar pesos.

Spec: docs/specs/2026-11-12-visao-pedestres-design.md
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

# ------------------------------------------------------------------------------------------ constantes (spec §6)
N_CONFIRMA = 3              # quadros seguidos para confirmar entrada/saída da faixa
TOLERANCIA_SUMICO_S = 1.0   # oclusão tolerada com o mesmo ID
TETO_S = 120                # acima disso: "acima_do_teto" (fora das médias)
VEL_IDOSO_MS = 1.2          # velocidade que os semáforos de SP supõem (Duim et al., 2017)
JANELA_CONFLITO_S = 1.0     # pedestre que saiu há até 1 s ainda conta no conflito
BLOQUEIO_S = 2.0            # veículo parado na faixa vazia por >= 2 s = bloqueio
MIN_QUADROS_PCD = 5         # quadros com auxílio colado para marcar a pessoa como PCD
CONF_MIN_AUXILIO = 0.25     # confiança mínima das classes de auxílio
SOBREPOSICAO_PCD = 0.3      # interseção ÷ área da caixa do auxílio
DIST_PCD_REL = 0.6          # distância entre centros ≤ 0,6 × altura da pessoa
FRACAO_CABECA = 0.25        # quarto superior da caixa da pessoa = cabeça (borrão)
LIMIAR_BORRAO = 0.25        # desvio-padrão da região borrada ≤ 25% do original

VEICULOS_CONFLITO = {"car", "motorcycle", "bus", "truck"}
AUXILIOS = {"wheelchair", "walker", "crutch", "cane"}
CHAVES_FAIXA = ("poligono", "resolucao", "lado_a", "lado_b", "comprimento_m")


@dataclass(frozen=True)
class Deteccao:
    quadro: int
    classe: str
    caixa: tuple[float, float, float, float]   # x1, y1, x2, y2 em pixels
    conf: float
    track_id: int | None = None


def ponto_da_pessoa(caixa) -> tuple[float, float]:
    """Ponto que decide se a pessoa está na faixa: o centro da BASE da caixa (os pés)."""
    x1, _, x2, y2 = caixa
    return ((x1 + x2) / 2, float(y2))


# ------------------------------------------------------------------------------------------ geometria
def _seg_cruza(p1, p2, q1, q2) -> bool:
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    o1, o2, o3, o4 = orient(p1, p2, q1), orient(p1, p2, q2), orient(q1, q2, p1), orient(q1, q2, p2)
    return o1 * o2 < 0 and o3 * o4 < 0


def _dist_segmento(p, a, b) -> float:
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


@dataclass(frozen=True)
class Faixa:
    poligono: list
    resolucao: tuple[int, int]
    lado_a: tuple[int, int]        # índices dos vértices da borda de calçada A
    lado_b: tuple[int, int]        # índices dos vértices da borda de calçada B
    comprimento_m: float           # distância real entre as calçadas (estimada, ver spec §6)

    def __post_init__(self):
        p = self.poligono
        if len(p) < 3:
            raise ValueError(f"o polígono da faixa precisa de pelo menos 3 pontos (tem {len(p)})")
        n = len(p)
        for i in range(n):
            for j in range(i + 1, n):
                if j == i + 1 or (i == 0 and j == n - 1):
                    continue          # lados vizinhos compartilham um vértice
                if _seg_cruza(p[i], p[(i + 1) % n], p[j], p[(j + 1) % n]):
                    raise ValueError(f"lados do polígono da faixa se cruzam (lados {i} e {j})")
        for nome in ("lado_a", "lado_b"):
            a, b = getattr(self, nome)
            if not (0 <= a < n and 0 <= b < n):
                raise ValueError(f"{nome} aponta para vértices inexistentes: {a, b}")
        if self.comprimento_m <= 0:
            raise ValueError("comprimento_m precisa ser positivo")

    @classmethod
    def de_dict(cls, d: dict) -> "Faixa":
        faltam = [k for k in CHAVES_FAIXA if k not in d]
        if faltam:
            raise ValueError(f"configuração da faixa sem a(s) chave(s): {', '.join(faltam)}")
        return cls(poligono=[tuple(map(float, v)) for v in d["poligono"]], resolucao=tuple(map(int, d["resolucao"])),
                   lado_a=tuple(map(int, d["lado_a"])), lado_b=tuple(map(int, d["lado_b"])),
                   comprimento_m=float(d["comprimento_m"]))

    @classmethod
    def carregar(cls, caminho) -> "Faixa":
        return cls.de_dict(json.loads(Path(caminho).read_text(encoding="utf-8")))

    def para_resolucao(self, largura: int, altura: int) -> "Faixa":
        """Reescala o polígono para outra resolução de MESMA proporção; proporção diferente → ValueError."""
        w0, h0 = self.resolucao
        if abs(largura / altura - w0 / h0) > 1e-3:
            raise ValueError(f"proporção do vídeo ({largura}×{altura}) diferente da faixa ({w0}×{h0}): "
                             "reconfigure o polígono para este vídeo")
        sx, sy = largura / w0, altura / h0
        return Faixa([(x * sx, y * sy) for x, y in self.poligono], (largura, altura), self.lado_a, self.lado_b,
                     self.comprimento_m)

    def contem(self, ponto) -> bool:
        """Ponto dentro do polígono (cruzamento de raio). A borda conta como dentro."""
        p, n = self.poligono, len(self.poligono)
        if any(_dist_segmento(ponto, p[i], p[(i + 1) % n]) <= 1e-6 for i in range(n)):
            return True
        x, y = ponto
        dentro = False
        for i in range(n):
            (x1, y1), (x2, y2) = p[i], p[(i + 1) % n]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                dentro = not dentro
        return dentro

    def lado_mais_proximo(self, ponto) -> str:
        p = self.poligono
        da = _dist_segmento(ponto, p[self.lado_a[0]], p[self.lado_a[1]])
        db = _dist_segmento(ponto, p[self.lado_b[0]], p[self.lado_b[1]])
        return "A" if da <= db else "B"
