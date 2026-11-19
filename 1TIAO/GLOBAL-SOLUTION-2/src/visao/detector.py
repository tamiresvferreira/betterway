"""Detector da faixa: YOLO-World (vocabulário aberto, sem treino) + rastreamento ByteTrack (Ultralytics).

É a única peça que importa o Ultralytics. Converte cada resultado em visao.Deteccao, para o resto do pipeline
(e os testes) não depender do modelo.
"""
from __future__ import annotations

from pathlib import Path

from visao import Deteccao, ler_video

PESOS = Path(__file__).resolve().parents[2] / "models" / "yolov8s-worldv2.pt"   # *.pt fica fora do Git
CLASSES_PADRAO = ["person", "car", "motorcycle", "bus", "truck", "bicycle", "wheelchair", "walker", "crutch", "cane",
                  "license plate", "zimmer frame", "walking cane"]
# termos extras que o modelo reconhece melhor (19/11: "zimmer frame" acha o andador a 0,38; "walker", não); viram o
# nome canônico, então o resto do sistema não muda
SINONIMOS = {"zimmer frame": "walker", "walking cane": "cane"}


def nome_canonico(nome: str) -> str:
    return SINONIMOS.get(nome, nome)


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
                dets.append(Deteccao(i, nome_canonico(r.names[c]), tuple(caixa), float(p), tid))
        yield i, img, dets
