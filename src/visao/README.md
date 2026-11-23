# Visão computacional na faixa de pedestres

Detecta pedestres e veículos num vídeo de câmera fixa, mede travessias, conflitos veículo × pedestre e bloqueios da
faixa, e grava eventos (só números) no banco `data/processed/seguranca_viaria.db`. Usa o **YOLO-World** (vocabulário
aberto, sem treino) com rastreamento **ByteTrack**.

**Estado (13/11/2026):** funcionando no vídeo de demonstração (Cidade do México, Pexels 25775484; ver
`data/raw/video/FONTE.md`), com resultados e leituras no notebook `07_visao_pedestres.ipynb`. A cadeira de rodas usa
também um **YOLO11s ajustado** (treinado no Colab, notebook 08), demonstrado em dois vídeos de cadeirante (notebook 09).

## Arquivos

| Arquivo | O que faz |
|---|---|
| `visao.py` | Regras (testadas): faixa, travessias, conflitos, bloqueios, auxílios de mobilidade, borrão, anotação, eventos |
| `detector.py` | Roda o YOLO-World + ByteTrack num vídeo e devolve as detecções quadro a quadro |
| `faixa_cdmx.json` | Polígono da faixa no vídeo, lados de entrada e saída e largura estimada (6,7 m) |
| `07_visao_pedestres.ipynb` | Pipeline completo, métricas, conferência visual, avaliação de PCD e eventos no banco |
| `08_ajuste_fino_colab.ipynb` | Ajuste fino no Google Colab (GPU): YOLO11s com `pedestre` e `pedestre_cadeira_rodas`; dados em `data/treino_pcd/FONTE.md` |
| `09_demo_cadeirante.ipynb` | Demonstração com dois vídeos de cadeirante: os dois modelos juntos, etiquetas e borrão pela pose |
| `baixar_avaliacao_pcd.py` | Baixa as 58 fotos do conjunto de avaliação de PCD (licenças em `data/avaliacao_pcd/FONTES.csv`) |

## Como rodar

```bash
# da raiz do repositório, com o .venv
.venv/Scripts/python.exe -m pytest tests/test_visao.py -q -m "not slow"   # testes das regras
.venv/Scripts/jupyter.exe nbconvert --to notebook --execute --inplace src/visao/07_visao_pedestres.ipynb
```

Pesos (fora do Git, em `models/`): `yolov8s-worldv2.pt` (baixado pelo ultralytics), `yolo11n-pose.pt` (idem) e
`pcd_yolo11s.pt` (gerado pelo notebook 08 no Colab).

O notebook usa o cache `data/processed/visao_deteccoes_cdmx.parquet` (caixas e classes, sem imagens). Sem o cache, ele
precisa do vídeo (link em `FONTE.md`) e dos pesos `models/yolov8s-worldv2.pt` (baixados pelo ultralytics), e leva uns
10 minutos em CPU.

## Regras principais

- **Ponto da pessoa:** centro da base da caixa (os pés). Está na faixa se esse ponto está dentro do polígono.
- **Travessia:** entra por um lado e sai pelo outro; status `concluida`, `retorno`, `nao_concluida`,
  `inicio_desconhecido` ou `acima_do_teto` (mais de 120 s). A velocidade só vale para as concluídas; acima de 3,5 m/s
  é marcada como incompatível com pedestre.
- **Conflito:** veículo **em movimento** a até 1 s de um pedestre na faixa; severidade alta se o pedestre usa auxílio
  de mobilidade ou o veículo está a 30 km/h ou mais. **Bloqueio:** veículo **parado** sobre a faixa por 2 s ou mais.
- **Condutores:** pessoa com metade ou mais da caixa dentro de uma moto ou bicicleta não conta como pedestre.
- **Auxílios de mobilidade:** cadeira de rodas, andador, muleta e bengala associados à pessoa por sobreposição e
  proximidade (limiar 0,10). A cadeira de rodas vem também do modelo ajustado (caixa = pessoa + cadeira). A pessoa é
  marcada se o auxílio estiver com ela em ≥ 5 quadros; o **acompanhante** que empurra (recebe a cadeira bem menos
  vezes que quem está sentado ao lado) não é marcado. "Bicicleta" que coincide com a cadeira é descartada.
  Só a cadeira de rodas é detectada com confiança. Os rótulos são descritivos e respeitosos
  ("Pedestre · cadeira de rodas"); a pessoa nunca é rotulada como "PCD".
- **Grupos na decisão, não na detecção:** cadeira, andador e muleta → mobilidade reduzida → **mais tempo**;
  bengala → orientação → **mais tempo e sinal sonoro** (bengala branca e de apoio não se distinguem bem); sem
  auxílio, mas abaixo de 1,2 m/s → **mais tempo**. O evento `pcd_na_faixa` leva auxílio, grupo e ações.

## Privacidade (LGPD)

Sem reconhecimento facial. Cabeças, rostos (localizados por um modelo de pose, para pegar quem está sentado ou em
close) e placas são pixelados **antes** de qualquer imagem ser salva, com bloco proporcional ao tamanho da pessoa (`salvar_quadro` e
`gravar_video_borrado` são as únicas funções que gravam imagem). O banco guarda só números e categorias, e os eventos
do vídeo de demonstração têm `demonstracao: true`. As fotos do conjunto de avaliação não vão para o Git.
