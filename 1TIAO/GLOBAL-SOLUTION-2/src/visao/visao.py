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
JANELA_MOV_S = 0.5          # janela para dizer se um veículo está em movimento
MOV_MIN_REL = 0.2           # em movimento: a base andou >= 20% da altura da caixa dentro da janela
VEL_CONFLITO_ALTA_KMH = 30  # conflito com veículo a >= 30 km/h na faixa = severidade alta
VEL_MAX_PEDESTRE_MS = 3.5   # travessia mais rápida que isso não é de pedestre andando (provável condutor não detectado)
MIN_QUADROS_PCD = 5         # quadros com auxílio colado para marcar a pessoa como PCD
CONF_MIN_AUXILIO = 0.10     # confiança mínima das classes de auxílio (0,10: 10/11 cadeirantes nas 58 fotos, sem alarme
                            # nas 25 negativas; errar para o lado de proteger. Escolhido nas mesmas fotos: otimista)
SOBREPOSICAO_PCD = 0.3      # interseção ÷ área da caixa do auxílio
DIST_PCD_REL = 0.6          # distância entre centros ≤ 0,6 × altura da pessoa
FRACAO_CABECA = 0.25        # quarto superior da caixa da pessoa = cabeça (borrão)
LIMIAR_BORRAO = 0.25        # desvio-padrão da região borrada ≤ 25% do original

VEICULOS_CONFLITO = {"car", "motorcycle", "bus", "truck"}
VEICULOS_MONTADOS = {"motorcycle", "bicycle"}     # quem está em cima é condutor, não pedestre
SOBREPOSICAO_CONDUTOR = 0.5                        # fração da caixa da pessoa dentro da caixa da moto/bicicleta
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

    def px_por_m(self) -> float:
        """Escala da faixa: distância entre os meios das bordas de calçada A e B ÷ comprimento real. Só vale perto da
        faixa (fora dela a perspectiva muda a escala)."""
        p = self.poligono
        (ax1, ay1), (ax2, ay2) = p[self.lado_a[0]], p[self.lado_a[1]]
        (bx1, by1), (bx2, by2) = p[self.lado_b[0]], p[self.lado_b[1]]
        return math.hypot((ax1 + ax2) / 2 - (bx1 + bx2) / 2, (ay1 + ay2) / 2 - (by1 + by2) / 2) / self.comprimento_m

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
    incompativel_pedestre: bool = False   # concluída rápido demais para quem anda (> VEL_MAX_PEDESTRE_MS)


def _validar_fps(fps) -> float:
    if fps is None or isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
        raise ValueError(f"fps inválido ({fps!r}): informe o fps do vídeo, maior que zero")
    return float(fps)


def _por_track(deteccoes, classe: str | None = "person") -> dict[int, list[Deteccao]]:
    """Detecções agrupadas por track_id, ordenadas por quadro, uma por quadro (a 1ª). classe=None: qualquer classe."""
    grupos: dict[int, dict[int, Deteccao]] = {}
    for d in deteccoes:
        if (classe is None or d.classe == classe) and d.track_id is not None:
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
                                   bool(vel is not None and vel < VEL_IDOSO_MS), tid in pcd_ids,
                                   bool(vel is not None and vel > VEL_MAX_PEDESTRE_MS)))

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


# ------------------------------------------------------------------------------------------ condutores
def sem_condutores(deteccoes) -> list[Deteccao]:
    """Remove as "pessoas" que são condutores de moto ou bicicleta: caixa da pessoa com ≥ SOBREPOSICAO_CONDUTOR da área
    dentro da caixa de uma moto/bicicleta no mesmo quadro. O detector marca o piloto como "person"; sem isso ele vira
    pedestre na faixa e a própria moto vira "conflito" com ele. Os veículos continuam na lista."""
    montados: dict[int, list] = {}
    for d in deteccoes:
        if d.classe in VEICULOS_MONTADOS:
            montados.setdefault(d.quadro, []).append(d.caixa)
    saida = []
    for d in deteccoes:
        if d.classe == "person" and _area(d.caixa) > 0 and any(
                _intersecao(d.caixa, v) / _area(d.caixa) >= SOBREPOSICAO_CONDUTOR for v in montados.get(d.quadro, [])):
            continue
        saida.append(d)
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


def auxilios_por_pessoa(deteccoes) -> dict[int, str]:
    """{track_id: auxílio mais frequente} das pessoas com auxílio de mobilidade colado em ≥ MIN_QUADROS_PCD quadros
    (uma detecção isolada não marca). Marcada, a pessoa vale assim no rastreamento todo."""
    por_quadro: dict[int, list[Deteccao]] = {}
    for d in deteccoes:
        por_quadro.setdefault(d.quadro, []).append(d)
    contagem: dict[int, dict[str, int]] = {}
    for dets in por_quadro.values():
        for tid, classe in associar_auxilios(dets).items():
            c = contagem.setdefault(tid, {})
            c[classe] = c.get(classe, 0) + 1
    return {t: max(c, key=c.get) for t, c in contagem.items() if sum(c.values()) >= MIN_QUADROS_PCD}


GRUPOS_AUXILIO = {"wheelchair": "mobilidade_reduzida", "walker": "mobilidade_reduzida",
                  "crutch": "mobilidade_reduzida", "cane": "orientacao"}
ACOES_GRUPO = {"mobilidade_reduzida": {"mais_tempo"},
               # a bengala branca (pessoa cega) e a de apoio não se distinguem bem na imagem: aciona as duas ações
               "orientacao": {"mais_tempo", "sinal_sonoro"}}


def grupo_do_auxilio(auxilio: str | None) -> str | None:
    """Agrupa na DECISÃO, não na detecção: o auxílio visto vira o grupo de necessidade na travessia."""
    return GRUPOS_AUXILIO.get(auxilio)


def acoes_na_faixa(auxilio: str | None, velocidade_ms: float | None) -> set[str]:
    """O que a faixa deve fazer pela pessoa: mais tempo (mobilidade reduzida, ou qualquer um abaixo de 1,2 m/s) e
    sinal sonoro (orientação). Sem auxílio e sem lentidão medida: nada."""
    acoes = set(ACOES_GRUPO.get(grupo_do_auxilio(auxilio), set()))
    if velocidade_ms is not None and velocidade_ms < VEL_IDOSO_MS:
        acoes.add("mais_tempo")
    return acoes


CONF_AJUSTADO = 0.25   # confiança mínima do modelo ajustado (YOLO11s, notebook 08) para "pedestre_cadeira_rodas"


def auxilios_do_ajustado(caixas, classes, confs, quadro: int) -> list[Deteccao]:
    """Converte a saída do modelo ajustado em detecções de auxílio 'wheelchair' (só a classe pedestre_cadeira_rodas,
    com confiança ≥ CONF_AJUSTADO). Nos vídeos de cadeirante ele etiquetou 90% e 82% dos quadros, contra 61% e 6% do
    YOLO-World."""
    return [Deteccao(quadro, "wheelchair", tuple(c), float(p), None)
            for c, k, p in zip(caixas, classes, confs) if k == "pedestre_cadeira_rodas" and p >= CONF_AJUSTADO]


def sem_bicicleta_na_cadeira(deteccoes) -> list[Deteccao]:
    """Tira as 'bicicletas' que são a própria cadeira de rodas (o YOLO-World confunde as rodas): bicicleta com metade ou
    mais da área dentro de uma cadeira de rodas do mesmo quadro. Sem isso, o cadeirante ganharia rótulo de bicicleta
    e poderia ser descartado como condutor."""
    cadeiras: dict[int, list] = {}
    for d in deteccoes:
        if d.classe == "wheelchair":
            cadeiras.setdefault(d.quadro, []).append(d.caixa)
    return [d for d in deteccoes
            if not (d.classe == "bicycle" and _area(d.caixa) > 0 and any(
                _intersecao(d.caixa, c) >= SOBREPOSICAO_CONDUTOR * _area(d.caixa) for c in cadeiras.get(d.quadro, [])))]


def pessoas_pcd(deteccoes) -> set[int]:
    """Pessoas (track_id) que usam auxílio de mobilidade (ver auxilios_por_pessoa)."""
    return set(auxilios_por_pessoa(deteccoes))


# ------------------------------------------------------------------------------------------ conflitos e bloqueios
@dataclass(frozen=True)
class Conflito:
    quadro: int
    track_veiculo: int
    classe_veiculo: str
    track_pedestre: int
    severidade: str          # "alta" (pedestre PCD ou veículo >= VEL_CONFLITO_ALTA_KMH) ou "normal"
    velocidade_kmh: float | None = None   # velocidade do veículo na faixa (escala da faixa)


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


def _veiculos_em_movimento(deteccoes, fps) -> dict[tuple[int, int], float]:
    """{(quadro, track_id): velocidade em px/s} dos veículos motorizados em movimento: a base da caixa andou
    ≥ MOV_MIN_REL × altura da caixa em relação à observação mais antiga dentro de JANELA_MOV_S. Sem observação anterior
    na janela = não se sabe = não conta como movimento."""
    janela = JANELA_MOV_S * fps
    movendo: dict[tuple[int, int], float] = {}
    for tid, dets in _por_track([d for d in deteccoes if d.classe in VEICULOS_CONFLITO], classe=None).items():
        for j, d in enumerate(dets):
            anteriores = [a for a in dets[:j] if d.quadro - a.quadro <= janela]
            if not anteriores:
                continue
            (x0, y0), (x1, y1) = ponto_da_pessoa(anteriores[0].caixa), ponto_da_pessoa(d.caixa)
            desloc = math.hypot(x1 - x0, y1 - y0)
            if desloc >= MOV_MIN_REL * (d.caixa[3] - d.caixa[1]):
                movendo[(d.quadro, tid)] = desloc * fps / (d.quadro - anteriores[0].quadro)
    return movendo


def conflitos(deteccoes, faixa: Faixa, fps, pcd_ids=frozenset()) -> list[Conflito]:
    """Veículo motorizado (carro, moto, ônibus, caminhão) EM MOVIMENTO na faixa enquanto há pedestre nela ou que saiu
    há no máximo JANELA_CONFLITO_S. Um conflito por par veículo × pedestre (deduplicado). Veículo parado na linha com
    pedestre passando à frente não é conflito; bicicleta não gera conflito."""
    fps = _validar_fps(fps)
    janela = JANELA_CONFLITO_S * fps
    movendo = _veiculos_em_movimento(deteccoes, fps)
    veic = {q: {t: c for t, c in v.items() if (q, t) in movendo}
            for q, v in _na_faixa(deteccoes, faixa, VEICULOS_CONFLITO).items()}
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
                    kmh = movendo[(q, tv)] / faixa.px_por_m() * 3.6
                    alta = tp in pcd_ids or kmh >= VEL_CONFLITO_ALTA_KMH
                    saida.append(Conflito(q, tv, classe, tp, "alta" if alta else "normal", round(kmh, 1)))
    return saida


def bloqueios(deteccoes, faixa: Faixa, fps) -> list[Bloqueio]:
    """Veículo motorizado PARADO na faixa SEM pedestre nela por ≥ BLOQUEIO_S seguidos: obriga o pedestre a desviar."""
    fps = _validar_fps(fps)
    minimo = BLOQUEIO_S * fps
    movendo = _veiculos_em_movimento(deteccoes, fps)
    veic = {q: {t: c for t, c in v.items() if (q, t) not in movendo}
            for q, v in _na_faixa(deteccoes, faixa, VEICULOS_CONFLITO).items()}
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


# ------------------------------------------------------------------------------------------ privacidade (LGPD)
BLOCO_PX = 10      # tamanho do bloco da pixelização; regiões menores que isso viram uma tarja de cor única
BLOCOS_MAX = 6                     # no máximo 6 blocos na largura da região: em close, o bloco cresce (rosto de 300 px fica irreconhecível)


CLASSES_PRIVADAS_INTEIRAS = {"license plate", "face"}   # borradas por inteiro (o rosto vem do vocabulário do YOLO-World)


PONTOS_ROSTO = (0, 1, 2, 3, 4)   # nariz, olhos e orelhas no padrão COCO de pose
CONF_PONTO_ROSTO = 0.3
FOLGA_ROSTO = 2.5                # a caixa do rosto é o vão entre os pontos multiplicado por isto
ROSTO_MIN_REL = 0.12             # ... e nunca menor que 12% da altura da pessoa (perfil, pontos colados)


def rostos_pela_pose(pontos_xy, pontos_conf, caixas_pessoa, quadro: int) -> list[Deteccao]:
    """Caixas 'face' a partir de um modelo de pose (nariz, olhos, orelhas). Em close, com a pessoa sentada ou cortada
    pela borda, a cabeça não está no quarto de cima da caixa; a pose acha o rosto onde ele estiver. Precisa de pelo
    menos 2 pontos do rosto com confiança ≥ CONF_PONTO_ROSTO (de costas, sem rosto visível, não gera caixa)."""
    rostos = []
    for xy, cf, caixa in zip(pontos_xy, pontos_conf, caixas_pessoa):
        pts = [tuple(xy[i]) for i in PONTOS_ROSTO if cf[i] >= CONF_PONTO_ROSTO]
        if len(pts) < 2:
            continue
        xs, ys = [x for x, _ in pts], [y for _, y in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        lado = max(FOLGA_ROSTO * max(max(xs) - min(xs), max(ys) - min(ys)), ROSTO_MIN_REL * (caixa[3] - caixa[1]))
        rostos.append(Deteccao(quadro, "face", (cx - lado / 2, cy - lado / 2, cx + lado / 2, cy + lado / 2), 1.0, None))
    return rostos


def _regioes_privadas(deteccoes_do_quadro, h: int, w: int) -> list[tuple[int, int, int, int]]:
    """(y1, y2, x1, x2) a borrar: quarto superior de cada pessoa (cabeça), cada rosto e cada placa, recortados à imagem."""
    regioes = []
    for d in deteccoes_do_quadro:
        x1, y1, x2, y2 = d.caixa
        if d.classe == "person":
            y2 = y1 + (y2 - y1) * FRACAO_CABECA
        elif d.classe not in CLASSES_PRIVADAS_INTEIRAS:
            continue
        r = (max(int(y1), 0), min(int(round(y2)), h), max(int(x1), 0), min(int(x2), w))
        if r[1] > r[0] and r[3] > r[2]:
            regioes.append(r)
    return regioes


def borrar(imagem, deteccoes_do_quadro):
    """Cópia da imagem com cabeças e placas pixelizadas (blocos de pelo menos BLOCO_PX, e no máximo BLOCOS_MAX
    blocos na largura da região). A entrada não é alterada."""
    import cv2
    out = imagem.copy()
    h, w = out.shape[:2]
    for y1, y2, x1, x2 in _regioes_privadas(deteccoes_do_quadro, h, w):
        reg = out[y1:y2, x1:x2]
        bloco = max(BLOCO_PX, -(-(x2 - x1) // BLOCOS_MAX))   # proporcional ao tamanho, nunca menor que BLOCO_PX
        pequeno = cv2.resize(reg, (max(1, -(-(x2 - x1) // bloco)), max(1, -(-(y2 - y1) // bloco))),
                             interpolation=cv2.INTER_AREA)
        out[y1:y2, x1:x2] = cv2.resize(pequeno, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
    return out


def salvar_quadro(imagem, deteccoes_do_quadro, caminho) -> Path:
    """ÚNICA forma de gravar um quadro em disco: sempre borra cabeças e placas antes."""
    import cv2
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(caminho), borrar(imagem, deteccoes_do_quadro)):
        raise OSError(f"não foi possível gravar {caminho}")
    return caminho


def gravar_video_borrado(quadros_e_deteccoes, caminho, fps) -> Path:
    """Grava um vídeo com cada quadro borrado. `quadros_e_deteccoes`: iterável de (imagem, deteccoes_do_quadro)."""
    import cv2
    fps = _validar_fps(fps)
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    escritor = None
    try:
        for img, dets in quadros_e_deteccoes:
            if escritor is None:
                h, w = img.shape[:2]
                escritor = cv2.VideoWriter(str(caminho), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            escritor.write(borrar(img, dets))
    finally:
        if escritor is not None:
            escritor.release()
    return caminho


# ------------------------------------------------------------------------------------------ eventos no banco
@dataclass(frozen=True)
class Evento:
    tipo: str
    quadro: int
    track_id: int | None
    valor: float | None
    payload: dict


def migrar(con) -> None:
    """Acrescenta à tabela `eventos` a coluna `chave` e o índice único, se faltarem (banco criado pelo notebook 03).
    Não apaga nada."""
    colunas = {r[1] for r in con.execute("PRAGMA table_info(eventos)")}
    with con:
        if "chave" not in colunas:
            con.execute("ALTER TABLE eventos ADD COLUMN chave TEXT")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_eventos_chave ON eventos(chave)")


def _primeiro_na_faixa(deteccoes, faixa) -> dict[int, int]:
    """track_id → primeiro quadro com os pés da pessoa na faixa."""
    primeiro: dict[int, int] = {}
    for d in deteccoes:
        if d.classe == "person" and d.track_id is not None and faixa.contem(ponto_da_pessoa(d.caixa)):
            primeiro[d.track_id] = min(primeiro.get(d.track_id, d.quadro), d.quadro)
    return primeiro


def eventos_de(travessias_, conflitos_, bloqueios_, pcd_ids, deteccoes, faixa: Faixa, fps) -> list[Evento]:
    """Eventos para a tabela `eventos`: pedestre_na_faixa e pcd_na_faixa (1º quadro de cada pessoa na faixa),
    travessia (com status), conflito_veiculo_pedestre (com severidade), bloqueio_faixa e contagem_minuto."""
    fps = _validar_fps(fps)
    ev = []
    aux = auxilios_por_pessoa(deteccoes)
    for tid, q in _primeiro_na_faixa(deteccoes, faixa).items():
        ev.append(Evento("pedestre_na_faixa", q, tid, None, {}))
        if tid in pcd_ids:
            a = aux.get(tid)
            ev.append(Evento("pcd_na_faixa", q, tid, None, {"auxilio": a, "grupo": grupo_do_auxilio(a),
                                                             "acoes": sorted(acoes_na_faixa(a, None))}))
    for t in travessias_:
        ev.append(Evento("travessia", t.quadro_inicio, t.track_id, t.duracao_s,
                         {"status": t.status, "quadro_fim": t.quadro_fim, "velocidade_ms": t.velocidade_ms,
                          "lado_entrada": t.lado_entrada, "lado_saida": t.lado_saida,
                          "abaixo_1_2_ms": t.abaixo_1_2_ms, "pcd": t.pcd,
                          "incompativel_pedestre": t.incompativel_pedestre}))
    for c in conflitos_:
        ev.append(Evento("conflito_veiculo_pedestre", c.quadro, c.track_veiculo, None,
                         {"track_pedestre": c.track_pedestre, "classe_veiculo": c.classe_veiculo,
                          "severidade": c.severidade, "velocidade_kmh": c.velocidade_kmh}))
    for b in bloqueios_:
        ev.append(Evento("bloqueio_faixa", b.quadro_inicio, b.track_veiculo, (b.quadro_fim - b.quadro_inicio + 1) / fps,
                         {"quadro_fim": b.quadro_fim}))
    por_min: dict[int, set] = {}
    for d in deteccoes:
        if d.classe == "person" and d.track_id is not None and faixa.contem(ponto_da_pessoa(d.caixa)):
            por_min.setdefault(int(d.quadro // (60 * fps)), set()).add(d.track_id)
    for m, ids in sorted(por_min.items()):
        ev.append(Evento("contagem_minuto", int(m * 60 * fps), None, float(len(ids)), {"minuto": m}))
    return ev


def _json_padrao(o):
    if hasattr(o, "item"):          # tipos numpy (np.int64, np.float32, ...)
        return o.item()
    raise TypeError(f"tipo não serializável: {type(o).__name__}")


def gravar_eventos(con, eventos, video_id: str, _substituir: bool = False) -> int:
    """Grava os eventos (origem 'yolo', marcados como demonstração) numa única transação e devolve quantos entraram.
    Reprocessar o mesmo vídeo não duplica (chave única); qualquer erro desfaz o lote inteiro."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")
    linhas = []
    for e in eventos:
        q = int(e.quadro)
        tid = None if e.track_id is None else int(e.track_id)
        extra = f":p{int(e.payload['track_pedestre'])}" if e.tipo == "conflito_veiculo_pedestre" else ""
        payload = {**e.payload, "demonstracao": True, "video_id": video_id, "quadro": q, "track_id": tid}
        linhas.append((agora, e.tipo, None if e.valor is None else float(e.valor),
                       json.dumps(payload, ensure_ascii=False, default=_json_padrao),
                       f"{video_id}:{q}:{tid}:{e.tipo}{extra}"))
    with con:   # transação: commit no fim, rollback em qualquer erro
        if _substituir:
            prefixo = f"{video_id}:"
            con.execute("DELETE FROM eventos WHERE origem = 'yolo' AND substr(chave, 1, ?) = ?",
                        (len(prefixo), prefixo))
        antes = con.total_changes
        con.executemany("INSERT INTO eventos (timestamp, origem, cluster_id, tipo, valor, payload_json, chave) "
                        "VALUES (?, 'yolo', NULL, ?, ?, ?, ?) ON CONFLICT(chave) DO NOTHING", linhas)
    return con.total_changes - antes


def substituir_eventos(con, eventos, video_id: str) -> int:
    """Reprocessamento de um vídeo: apaga os eventos anteriores DESTE vídeo e grava os novos, na mesma transação
    (se a gravação falhar, os antigos voltam). Evita que execuções com parâmetros antigos fiquem no banco."""
    return gravar_eventos(con, eventos, video_id, _substituir=True)


# ------------------------------------------------------------------------------------------ leitura de vídeo
def ler_video(caminho):
    """(fps, largura, altura, gerador de quadros BGR). Lê em fluxo, sem carregar o vídeo na memória.
    Inexistente → FileNotFoundError; vazio, corrompido ou sem fps → ValueError."""
    import cv2
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"vídeo não encontrado: {caminho}")
    if caminho.stat().st_size == 0:
        raise ValueError(f"vídeo vazio (0 bytes): {caminho}")
    cap = cv2.VideoCapture(str(caminho))
    try:
        ok, quadro = cap.read() if cap.isOpened() else (False, None)
        if not ok or quadro is None:
            raise ValueError(f"vídeo corrompido ou ilegível: {caminho}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        largura, altura = quadro.shape[1], quadro.shape[0]
    finally:
        cap.release()
    if not fps or fps <= 0 or not math.isfinite(fps):
        raise ValueError(f"vídeo sem fps válido nos metadados: {caminho}")

    def quadros():
        c = cv2.VideoCapture(str(caminho))
        try:
            while True:
                ok, q = c.read()
                if not ok:
                    return
                yield q
        finally:
            c.release()

    return float(fps), largura, altura, quadros()


# ------------------------------------------------------------------------------------------ anotação visual
ROTULOS_VEICULO = {"car": "Carro", "motorcycle": "Moto", "bus": "Ônibus", "truck": "Caminhão", "bicycle": "Bicicleta"}
ROTULOS_AUXILIO = {"wheelchair": "cadeira de rodas", "walker": "andador", "crutch": "muleta", "cane": "bengala"}
COR_PEDESTRE = (52, 104, 235)      # laranja forte (BGR) — mesma família de cor dos gráficos
COR_CONFLITO = (40, 40, 220)       # vermelho
COR_VEICULO = (214, 120, 42)       # azul
COR_FORA = (170, 170, 170)         # cinza: pessoa fora da faixa
COR_FAIXA = (0, 230, 255)          # amarelo
VEIC_ROTULO_MIN_ALT = 0.08         # veículo com caixa menor que 8% da altura da imagem (ao fundo): sem rótulo


@dataclass(frozen=True)
class ItemAnotacao:
    caixa: tuple
    cor: tuple
    grossa: bool
    texto: str | None
    track_id: int | None


def rotulo(d: Deteccao, na_faixa: bool, auxilio: str | None = None, conflito_kmh: float | None = None) -> str | None:
    """Texto curto e respeitoso para a caixa: descreve o auxílio que a pessoa usa, não uma condição dela.
    Pessoa fora da faixa e placas não recebem rótulo."""
    if d.classe == "person":
        if not na_faixa:
            return None
        return "Pedestre" + (f" · {ROTULOS_AUXILIO[auxilio]}" if auxilio in ROTULOS_AUXILIO else "")
    if d.classe in ROTULOS_VEICULO:
        return ROTULOS_VEICULO[d.classe] + (f" · {conflito_kmh:.0f} km/h" if conflito_kmh is not None else "")
    return None


def _fonte(tamanho: int):
    from PIL import ImageFont
    from matplotlib import font_manager
    return ImageFont.truetype(font_manager.findfont("DejaVu Sans"), tamanho)


def itens_anotacao(deteccoes_do_quadro, faixa: Faixa | None, auxilios: dict[int, str] | None = None,
                   conflitos_kmh: dict[int, float] | None = None, altura_img: int | None = None) -> list[ItemAnotacao]:
    """O que desenhar num quadro (sem desenhar): condutores de moto/bicicleta não viram "Pedestre" (o veículo é que
    recebe o rótulo); veículos pequenos, ao fundo, ficam só com a caixa, sem rótulo, para não poluir."""
    auxilios, conflitos_kmh = auxilios or {}, conflitos_kmh or {}
    # faixa=None: demonstração sem faixa (vídeo de calçada) — toda pessoa é tratada como pedestre
    altura_img = altura_img or (faixa.resolucao[1] if faixa is not None else None)
    itens = []
    for d in sem_condutores(deteccoes_do_quadro):
        if d.classe == "person":
            dentro = faixa is None or faixa.contem(ponto_da_pessoa(d.caixa))
            itens.append(ItemAnotacao(d.caixa, COR_PEDESTRE if dentro else COR_FORA, dentro,
                                      rotulo(d, dentro, auxilios.get(d.track_id)), d.track_id))
        elif d.classe in ROTULOS_VEICULO:
            kmh = conflitos_kmh.get(d.track_id)
            grande = altura_img is None or (d.caixa[3] - d.caixa[1]) >= VEIC_ROTULO_MIN_ALT * altura_img
            txt = rotulo(d, False, conflito_kmh=kmh) if (grande or kmh is not None) else None
            itens.append(ItemAnotacao(d.caixa, COR_CONFLITO if kmh is not None else COR_VEICULO, kmh is not None,
                                      txt, d.track_id))
    return itens


def anotar(imagem, deteccoes_do_quadro, faixa: Faixa | None, auxilios: dict[int, str] | None = None,
           conflitos_kmh: dict[int, float] | None = None, privadas_extra=()):
    """Cópia da imagem para mostrar (vídeo, GIF, PDF): PRIMEIRO borra cabeças e placas, DEPOIS desenha a faixa, as
    caixas e os rótulos (nítidos por cima). Pessoa na faixa: caixa laranja grossa + "Pedestre" (com o auxílio, se
    houver); fora da faixa: caixa cinza fina, sem rótulo; veículo: azul; veículo em conflito: vermelho + km/h.
    `auxilios`: {track_id: classe do auxílio}; `conflitos_kmh`: {track_id do veículo: km/h}."""
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw
    # borra TODAS as pessoas (inclusive condutores), placas e as regiões extras (rostos pela pose, pessoas de outro
    # modelo), que não viram caixa nem rótulo
    out = borrar(imagem, [*deteccoes_do_quadro, *privadas_extra])
    h = out.shape[0]
    grossa, fina = max(3, h // 240), max(2, h // 600)
    if faixa is not None:
        cv2.polylines(out, [np.array(faixa.poligono, np.int32)], True, COR_FAIXA, max(2, h // 480))
    textos = []
    for it in itens_anotacao(deteccoes_do_quadro, faixa, auxilios, conflitos_kmh, altura_img=h):
        x1, y1, x2, y2 = map(int, it.caixa)
        cv2.rectangle(out, (x1, y1), (x2, y2), it.cor, grossa if it.grossa else fina)
        if it.texto:
            textos.append((it.texto, x1, y1, it.cor))
    if textos:
        pil = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
        desenho, fonte = ImageDraw.Draw(pil), _fonte(max(14, h // 55))
        for txt, x1, y1, cor in textos:
            l, t, r, b = desenho.textbbox((0, 0), txt, font=fonte)
            x0, y0 = max(0, x1), max(0, y1 - (b - t) - 8)
            desenho.rectangle((x0, y0, x0 + (r - l) + 8, y0 + (b - t) + 8), fill=cor[::-1])
            desenho.text((x0 + 4 - l, y0 + 4 - t), txt, font=fonte, fill=(255, 255, 255))
        out = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return out
