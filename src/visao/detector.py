"""Detector da faixa: YOLO-World (vocabulário aberto, sem treino) + rastreamento ByteTrack (Ultralytics).

É a única peça que importa o Ultralytics. Converte cada resultado em visao.Deteccao, para o resto do pipeline
(e os testes) não depender do modelo.
"""
from __future__ import annotations

from pathlib import Path

from visao import Deteccao, ler_video

PESOS = Path(__file__).resolve().parents[2] / "models" / "yolov8s-worldv2.pt"   # *.pt fica fora do Git
CLASSES_PADRAO = ["person", "car", "motorcycle", "bus", "truck", "bicycle", "wheelchair", "walker", "crutch", "cane",
                  "license plate", "zimmer frame", "walking cane", "ambulance"]
# termos extras que o modelo reconhece melhor (19/11: "zimmer frame" acha o andador a 0,38; "walker", não); viram o
# nome canônico, então o resto do sistema não muda
SINONIMOS = {"zimmer frame": "walker", "walking cane": "cane"}


def nome_canonico(nome: str) -> str:
    return SINONIMOS.get(nome, nome)


# O YOLO-World não reconhece ambulância (sempre sai "bus" ou "truck"). Regra de cor nos veículos grandes: branco com faixa
# vermelha, o padrão das viaturas do SAMU. Calibrada em 19/11 nos clipes: ambulância 5 a 27% de vermelho; demais
# veículos grandes (inclusive vans brancas) até 1,1%. Em produção, um modelo ajustado com fotos de ambulância.
GRANDES = {"bus", "truck", "van"}
MIN_VERMELHO, MIN_BRANCO = 0.04, 0.10


def _iou(a, b) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    uniao = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / uniao if uniao > 0 else 0.0


def sem_duplicatas_da_ambulancia(dets: list, limiar: float = 0.5) -> list:
    """O modelo costuma achar o mesmo veículo duas vezes (carro e ônibus, por exemplo). Sobre a caixa de uma
    ambulância, fica só ela (a de maior confiança): as outras caixas de veículo que a cobrem saem."""
    ambs = sorted((d for d in dets if d.classe == "ambulance"), key=lambda d: -d.conf)
    mantidas = []
    for a in ambs:
        if all(_iou(a.caixa, m.caixa) < limiar for m in mantidas):
            mantidas.append(a)
    veiculos = {"car", "bus", "truck", "motorcycle", "ambulance"}
    resto = [d for d in dets if d.classe != "ambulance" and
             not (d.classe in veiculos and any(_iou(d.caixa, m.caixa) >= limiar for m in mantidas))]
    return resto + mantidas


def parece_ambulancia(recorte) -> bool:
    import cv2
    if recorte is None or recorte.size == 0:
        return False
    hsv = cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV)
    h, s_, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    vermelho = (((h < 10) | (h > 170)) & (s_ > 120) & (v > 90)).mean()
    branco = ((s_ < 40) & (v > 170)).mean()
    return bool(vermelho >= MIN_VERMELHO and branco >= MIN_BRANCO)


def detectar(caminho_video, classes=CLASSES_PADRAO, a_cada: int = 1, conf: float = 0.1, pesos=PESOS):
    """Gera (índice do quadro, imagem BGR, lista de Deteccao) para 1 a cada `a_cada` quadros do vídeo.

    O índice é o do vídeo original (com a_cada > 1 os quadros pulados simplesmente não aparecem; as funções de
    travessia usam o índice e o fps original). `conf` baixo de propósito: o filtro de confiança dos auxílios fica em
    visao.CONF_MIN_AUXILIO (0,10), calibrado no conjunto de avaliação.
    """
    from ultralytics import YOLOWorld
    if a_cada < 1:
        raise ValueError("a_cada precisa ser ≥ 1")
    Path(pesos).parent.mkdir(parents=True, exist_ok=True)
    modelo = YOLOWorld(str(pesos))
    modelo.set_classes(list(classes))
    _, _, _, quadros = ler_video(caminho_video)
    for i, img in enumerate(quadros):
        if i % a_cada:
            continue
        r = modelo.track(img, persist=True, tracker="bytetrack.yaml", conf=conf, verbose=False)[0]
        dets = []
        if r.boxes is not None and len(r.boxes):
            ids = r.boxes.id.int().tolist() if r.boxes.id is not None else [None] * len(r.boxes)
            for caixa, c, p, tid in zip(r.boxes.xyxy.tolist(), r.boxes.cls.int().tolist(), r.boxes.conf.tolist(), ids):
                nome = nome_canonico(r.names[c])
                if nome in GRANDES:
                    x1, y1, x2, y2 = (int(v) for v in caixa)
                    if parece_ambulancia(img[max(0, y1):y2, max(0, x1):x2]):
                        nome = "ambulance"
                dets.append(Deteccao(i, nome, tuple(caixa), float(p), tid))
        yield i, img, sem_duplicatas_da_ambulancia(dets)
