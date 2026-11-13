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


# ------------------------------------------------------------------------------------------ travessias
@dataclass(frozen=True)
class Travessia:
    track_id: int
    quadro_inicio: int
    quadro_fim: int
    duracao_s: float
    velocidade_ms: float | None     # só para "concluida": comprimento da faixa ÷ duração
    lado_entrada: str | None        # "A", "B" ou None (início desconhecido)
    lado_saida: str | None          # "A", "B" ou None (não saiu)
    status: str                     # concluida | retorno | nao_concluida | inicio_desconhecido | acima_do_teto
    abaixo_1_2_ms: bool
    pcd: bool


def _validar_fps(fps) -> float:
    if fps is None or isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
        raise ValueError(f"fps inválido ({fps!r}): informe o fps do vídeo, maior que zero")
    return float(fps)


def _por_track(deteccoes, classe="person") -> dict[int, list[Deteccao]]:
    """Detecções de uma classe agrupadas por track_id, ordenadas por quadro, uma por quadro (a 1ª)."""
    grupos: dict[int, dict[int, Deteccao]] = {}
    for d in deteccoes:
        if d.classe == classe and d.track_id is not None:
            grupos.setdefault(d.track_id, {}).setdefault(d.quadro, d)
    return {t: [q[k] for k in sorted(q)] for t, q in grupos.items()}


def travessias(deteccoes, faixa: Faixa, fps, pcd_ids=frozenset()) -> list[Travessia]:
    """Travessias de cada pessoa rastreada (ver spec §5, itens 6–14, e §6).

    Máquina de estados por track_id: um estado (dentro/fora) só muda depois de N_CONFIRMA quadros observados
    seguidos no novo estado (filtra o tremor na borda). Sumiço maior que TOLERANCIA_SUMICO_S encerra a travessia em
    curso como "nao_concluida"; se a pessoa já estava dentro quando apareceu, o início é desconhecido.
    """
    fps = _validar_fps(fps)
    max_gap = TOLERANCIA_SUMICO_S * fps
    saida = []
    for tid, dets in _por_track(deteccoes).items():
        pts = [ponto_da_pessoa(d.caixa) for d in dets]
        dentro = [faixa.contem(p) for p in pts]
        quadros = [d.quadro for d in dets]
        estado = None            # None = ainda não confirmado; True = dentro; False = fora
        atual = None             # travessia em curso: dict(inicio, lado_entrada, ultimo)
        corrida, corrida_ini = 0, 0

        def fechar(fim_quadro, lado_saida, motivo=None):
            ini = atual["inicio"]
            dur = (fim_quadro - ini + 1) / fps
            if motivo:
                status = motivo
            elif atual["lado_entrada"] is None:
                status = "inicio_desconhecido"
            elif dur > TETO_S:
                status = "acima_do_teto"
            elif lado_saida == atual["lado_entrada"]:
                status = "retorno"
            else:
                status = "concluida"
            vel = faixa.comprimento_m / dur if status == "concluida" else None
            saida.append(Travessia(tid, ini, fim_quadro, dur, vel, atual["lado_entrada"], lado_saida, status,
                                   bool(vel is not None and vel < VEL_IDOSO_MS), tid in pcd_ids))

        for i, (q, den) in enumerate(zip(quadros, dentro)):
            if i > 0 and q - quadros[i - 1] - 1 > max_gap:          # sumiço longo
                if atual is not None:
                    fechar(atual["ultimo"], None, "nao_concluida")
                    atual = None
                estado, corrida = None, 0
            # corrida de quadros no mesmo estado observado
            if i > 0 and den == dentro[i - 1] and not (q - quadros[i - 1] - 1 > max_gap):
                corrida += 1
            else:
                corrida, corrida_ini = 1, i
            if den and atual is not None:
                atual["ultimo"] = q
            if corrida >= N_CONFIRMA and den != estado:
                if den:   # entrada confirmada
                    lado = faixa.lado_mais_proximo(pts[corrida_ini]) if estado is False else None
                    ultimo_dentro = max(quadros[j] for j in range(corrida_ini, i + 1))
                    atual = {"inicio": quadros[corrida_ini], "lado_entrada": lado, "ultimo": ultimo_dentro}
                elif atual is not None:   # saída confirmada
                    fechar(atual["ultimo"], faixa.lado_mais_proximo(pts[corrida_ini]))
                    atual = None
                estado = den
        if atual is not None:                                       # vídeo/rastreamento acabou com a pessoa dentro
            fechar(atual["ultimo"], None, "nao_concluida")
    return saida


# ------------------------------------------------------------------------------------------ PCD
def _area(c) -> float:
    return max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])


def _intersecao(a, b) -> float:
    return _area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def _centro(c) -> tuple[float, float]:
    return ((c[0] + c[2]) / 2, (c[1] + c[3]) / 2)


def associar_auxilios(deteccoes_do_quadro) -> dict[int, str]:
    """Num quadro: qual pessoa rastreada está com cada auxílio de mobilidade (cadeira de rodas, andador, muleta,
    bengala). Regra relativa ao tamanho (vale perto e longe da câmera): interseção ÷ área do auxílio ≥
    SOBREPOSICAO_PCD e distância entre centros ≤ DIST_PCD_REL × altura da pessoa. Se mais de uma pessoa servir
    (acompanhante), fica a de maior sobreposição. Auxílio sem ninguém perto não cria pessoa."""
    pessoas = [d for d in deteccoes_do_quadro if d.classe == "person" and d.track_id is not None]
    marcadas: dict[int, str] = {}
    for a in deteccoes_do_quadro:
        if a.classe not in AUXILIOS or a.conf < CONF_MIN_AUXILIO or _area(a.caixa) == 0:
            continue
        melhor, melhor_sob = None, 0.0
        for p in pessoas:
            sob = _intersecao(p.caixa, a.caixa) / _area(a.caixa)
            (cx, cy), (ax, ay) = _centro(p.caixa), _centro(a.caixa)
            perto = math.hypot(cx - ax, cy - ay) <= DIST_PCD_REL * (p.caixa[3] - p.caixa[1])
            if sob >= SOBREPOSICAO_PCD and perto and sob > melhor_sob:
                melhor, melhor_sob = p.track_id, sob
        if melhor is not None:
            marcadas[melhor] = a.classe
    return marcadas


def pessoas_pcd(deteccoes) -> set[int]:
    """Pessoas (track_id) com auxílio de mobilidade colado em ≥ MIN_QUADROS_PCD quadros (uma detecção isolada não
    marca). Marcada, a pessoa vale como PCD no rastreamento todo."""
    por_quadro: dict[int, list[Deteccao]] = {}
    for d in deteccoes:
        por_quadro.setdefault(d.quadro, []).append(d)
    contagem: dict[int, int] = {}
    for dets in por_quadro.values():
        for tid in associar_auxilios(dets):
            contagem[tid] = contagem.get(tid, 0) + 1
    return {t for t, n in contagem.items() if n >= MIN_QUADROS_PCD}


# ------------------------------------------------------------------------------------------ conflitos e bloqueios
@dataclass(frozen=True)
class Conflito:
    quadro: int
    track_veiculo: int
    classe_veiculo: str
    track_pedestre: int
    severidade: str          # "alta" (pedestre PCD) ou "normal"


@dataclass(frozen=True)
class Bloqueio:
    quadro_inicio: int
    quadro_fim: int
    track_veiculo: int


def _na_faixa(deteccoes, faixa: Faixa, classes) -> dict[int, dict[int, str]]:
    """quadro → {track_id: classe} dos objetos das classes dadas com o ponto da base dentro da faixa."""
    out: dict[int, dict[int, str]] = {}
    for d in deteccoes:
        if d.classe in classes and d.track_id is not None and faixa.contem(ponto_da_pessoa(d.caixa)):
            out.setdefault(d.quadro, {})[d.track_id] = d.classe
    return out


def conflitos(deteccoes, faixa: Faixa, fps, pcd_ids=frozenset()) -> list[Conflito]:
    """Veículo motorizado (carro, moto, ônibus, caminhão) na faixa enquanto há pedestre nela ou que saiu há no
    máximo JANELA_CONFLITO_S. Um conflito por par veículo × pedestre (deduplicado). Bicicleta não gera conflito."""
    fps = _validar_fps(fps)
    janela = JANELA_CONFLITO_S * fps
    veic = _na_faixa(deteccoes, faixa, VEICULOS_CONFLITO)
    ped = _na_faixa(deteccoes, faixa, {"person"})
    ultimo_dentro: dict[int, int] = {}
    vistos, saida = set(), []
    for q in sorted(set(veic) | set(ped)):
        for tid in ped.get(q, {}):
            ultimo_dentro[tid] = q
        for tv, classe in veic.get(q, {}).items():
            for tp, ult in ultimo_dentro.items():
                if q - ult <= janela and (tv, tp) not in vistos:
                    vistos.add((tv, tp))
                    saida.append(Conflito(q, tv, classe, tp, "alta" if tp in pcd_ids else "normal"))
    return saida


def bloqueios(deteccoes, faixa: Faixa, fps) -> list[Bloqueio]:
    """Veículo motorizado na faixa SEM pedestre nela por ≥ BLOQUEIO_S seguidos: obriga o pedestre a desviar."""
    fps = _validar_fps(fps)
    minimo = BLOQUEIO_S * fps
    veic = _na_faixa(deteccoes, faixa, VEICULOS_CONFLITO)
    ped = _na_faixa(deteccoes, faixa, {"person"})
    corridas: dict[int, list[int]] = {}
    saida = []

    def encerrar(tv):
        q = corridas.pop(tv)
        if q[1] - q[0] + 1 >= minimo:
            saida.append(Bloqueio(q[0], q[1], tv))

    for q in sorted(veic):
        livres = set() if ped.get(q) else set(veic[q])
        for tv in list(corridas):
            if tv not in livres or corridas[tv][1] != q - 1:
                encerrar(tv)
        for tv in livres:
            corridas.setdefault(tv, [q, q])[1] = q
    for tv in list(corridas):
        encerrar(tv)
    return saida


def contagem_bicicletas(deteccoes, faixa: Faixa) -> int:
    """Bicicletas (ids únicos) que passaram pela faixa: contadas à parte, não geram conflito."""
    return len({tid for q in _na_faixa(deteccoes, faixa, {"bicycle"}).values() for tid in q})
