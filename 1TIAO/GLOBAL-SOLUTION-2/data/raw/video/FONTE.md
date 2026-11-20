# Vídeo usado no módulo de visão (base de demonstração)

| Campo | Valor |
|---|---|
| Arquivo local | `cdmx_faixa_pexels_25775484.mp4` (fora do Git; baixe pelo link abaixo) |
| Título | A Crosswalk in a City with Cars and People |
| Onde | Rua com faixa de pedestres, ao que tudo indica na Cidade do México (cena latino-americana); câmera fixa na altura da rua |
| Autor | Anya Juárez Tenorio |
| Fonte | Pexels: https://www.pexels.com/video/a-crosswalk-in-a-city-with-cars-and-people-25775484/ |
| Arquivo baixado | https://videos.pexels.com/video-files/25775484/11908131_1080_1920_30fps.mp4 |
| Licença | **Licença Pexels**: uso livre e gratuito, sem exigência de crédito (https://www.pexels.com/license/). Damos o crédito mesmo assim |
| Formato | 1080 × 1920 (vertical), 30 fps, 55 s, dia |
| Baixado em | 12/11/2026 |

**Por que este vídeo:** câmera parada, de dia, faixa de pedestres em primeiro plano, várias travessias em 55 s
(pedestres, uma bicicleta, uma moto, carros parados na linha de retenção) e pessoas grandes o bastante para o
detector. Não é o Largo da Concórdia, então tudo que sair dele é **demonstração** (regra 8 da GS), marcado assim no
banco (`payload_json`) e no PDF.

**Limitação de enquadramento:** o quadro vertical mostra só o trecho da faixa que cabe na imagem, não a rua inteira
de calçada a calçada. A "travessia" medida é a do trecho visível (da borda esquerda à direita do quadro), e o
largura visível da faixa (~8 m) é estimada pelo número de listras; o polígono usado vai de x=90 a x=990 (6,7 m), recuado das bordas para que a pessoa seja vista entrando e saindo.

**Descartados (com motivo):**
- **Shibuya Crossing**, Tóquio (Wikimedia Commons, CC BY 2.0, Emran Kassim). Foi o 1º escolhido e o notebook chegou a
  rodar com ele, mas o YOLO-World encontrou só 30 pessoas no vídeo inteiro. O diagnóstico testou o YOLO-World com 11
  classes e só com "person", o YOLOv8 COCO, a resolução 1280 e o recorte ampliado da faixa: todos acham 5 a 9 pessoas
  num quadro com ~300. A causa é a multidão densa e sobreposta, em 640×480 à noite, que o detector não separa. O vídeo
  é inadequado para medir travessias individuais.
- Eje Central × Madero, Cidade do México (Commons, CC BY-SA 4.0): multidão densa e ângulo baixo.
- Katella Avenue, Anaheim (Commons, CC0): mostra só uma botoeira.
- Yonge-Dundas, Toronto (Commons, CC0): câmera na altura da rua, em movimento.
- Tomaszów Mazowiecki, Polônia (Commons, domínio público): 12 s, sem travessias.
- Pexels 5009493 e 4095209: câmera em movimento, sem pedestres ou filmado à mão.
- Pexels 30935166 (drone): câmera em movimento; pessoas vistas de cima viram pontos.
- Pexels 39134141, 30347779 e 36306797: câmera em movimento (medido pela diferença entre quadros).

# Vídeos da demonstração de pedestre com cadeira de rodas (notebook 09)

| Arquivo local (fora do Git) | Pexels | Cena | Formato |
|---|---|---|---|
| `cadeirante_pexels_6646677.mp4` | https://www.pexels.com/video/a-man-riding-a-wheelchair-6646677/ | homem em cadeira de rodas, empurrado por uma acompanhante, de frente e de lado | 1920×1080, 24 fps, 10,9 s |
| `cadeirante_pexels_6646724.mp4` | https://www.pexels.com/video/6646724/ | o mesmo homem, de costas, em close, empurrado por um acompanhante | 1920×1080, 24 fps, 10,4 s |

Licença **Pexels** (uso livre, sem exigência de crédito; damos o crédito mesmo assim). Baixados em 13/11/2026.

**Limitação:** a câmera acompanha as pessoas (deslocamento mediano de 25 e 45 px a cada 0,5 s, em 640 px de largura)
e não há faixa de pedestres. Os vídeos servem só para **mostrar a identificação** do pedestre com cadeira de rodas,
não para medir travessia.

**Descartado como demonstração de PCD:** Pexels 8126402 (dois senhores atravessando em Los Angeles, câmera em
movimento): andam normalmente, sem auxílio de mobilidade; não serve para mostrar "dificuldade motora", e inferir
isso pela aparência seria errado (e dado sensível).
