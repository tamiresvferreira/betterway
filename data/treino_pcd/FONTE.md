# Dados de treino do ajuste fino (pedestre com cadeira de rodas)

| Campo | Valor |
|---|---|
| Dataset | Roboflow Universe, projeto *crooswalk/wheelchair-tmzbn*, versão 2 |
| Link | https://universe.roboflow.com/crooswalk/wheelchair-tmzbn/dataset/2 |
| Licença | **CC BY 4.0** (crédito ao autor do dataset no Roboflow Universe) |
| Arquivo | `wheelchair.v2i.yolov8.zip` (formato YOLOv8), baixado em 13/11/2026; **fora do Git** |
| Conteúdo | 512 imagens (359 treino, 103 validação, 50 teste), redimensionadas para 640×640 |
| Classes | `people` → `pedestre` (554 caixas); `peopleWithWheelchair` → `pedestre_cadeira_rodas` (679 caixas) |

A caixa de `peopleWithWheelchair` cobre a pessoa **e** a cadeira. As imagens foram coletadas da internet (fotos de
notícia, miniaturas de vídeo, esporte em cadeira de rodas) por quem montou o dataset; usamos para fins acadêmicos,
com crédito, e não redistribuímos.

**Conferências (13/11/2026):** nenhuma das 58 fotos de avaliação (`data/avaliacao_pcd/`) tem duplicata no dataset
(hash perceptual, distância ≤ 12); 8 das 503 caixas de `people` (treino + validação) têm uma cadeira de rodas dentro,
em parte acompanhantes empurrando a cadeira.

**Descartado:** *car-numbers/wheelchair-vrjdr* v1 (CC BY 4.0, 100 imagens): todas as caixas marcam **cadeiras vazias**,
pequenas e distantes, sem pessoa; ensinaria o modelo a achar cadeira abandonada, não pedestre com cadeira.

Treino: `src/visao/08_ajuste_fino_colab.ipynb` (Google Colab, GPU).
