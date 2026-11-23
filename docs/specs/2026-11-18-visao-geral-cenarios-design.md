# Visão geral em quatro cenários (sem rolagem): design

Data: 18/11/2026 · Entrega da GS: 19/11/2026, 18h

## 1. Objetivo

A Visão geral passa a explicar **o mecanismo** a quem chega na plataforma: o que a câmera vê e o que o sistema faz
por trás. Cada cenário é um *take* (trecho de vídeo do Veo 3) ao lado da simulação Hoje × Com a BetterWay.
Não há seleção, registro nem ocorrência aqui; o acompanhamento ao vivo continua na área **Câmeras**, sem mudança.

**Sucesso:** os quatro cenários aparecem um por vez, cada um cabendo numa tela de notebook (cerca de 1366 × 768) sem
rolar; a seta troca o cenário com uma animação curta; enquanto o vídeo de um cenário não existe, aparece um espaço
reservado no lugar.

## 2. Cenários (ordem fixa)

| # | Pilar (verbo) | Ícone | Título | Simulação (`cruzamento.carregar`) | Vídeo esperado |
|---|---|---|---|---|---|
| 1 | to live | `vida` | Ninguém fica na faixa com os carros em verde | `conflito` | `visao_geral_conflito.mp4` |
| 2 | to move | `rota` | Faz o trânsito andar | `transito` | `visao_geral_transito.mp4` |
| 3 | to move | `rota` | Abre caminho para a ambulância | `ambulancia` | `visao_geral_ambulancia.mp4` |
| 4 | to be free | `pedestre` | Dá tempo a quem precisa atravessar | `pedestre` | `visao_geral_pedestre.mp4` |

Os textos curtos de cada cenário são os que a Visão geral já usa hoje (sem travessões); a Tamires revisa depois.
Vídeo 3: a ambulância chega no vermelho, encontra os carros já afastados (alerta aos motoristas à frente) e passa
direto.

## 3. Layout de um cenário

```
[ cabeçalho baixo: chamada da BetterWay em uma linha ]
[ verbo · título ]                                     
[ texto curto (1 a 2 linhas) ]
+----------------------+  +------------------------------+   ( > )
|  vídeo do cenário    |  |  simulação Hoje × BetterWay  |   seta
|  (ou espaço reserv.) |  |                              |
+----------------------+  +------------------------------+
                 ●  ○  ○  ○      1 de 4
```

- Vídeo à esquerda ("o que a câmera vê"), simulação à direita ("o que o sistema faz"). Em tela estreita
  (≤ 760 px), um embaixo do outro: aí a rolagem é aceitável.
- **Espaço reservado:** caixa cinza com o texto "Vídeo do cenário em breve" e o nome do arquivo esperado, na
  proporção 16:9.
- **Vídeo presente:** `<video>` mudo, em loop, `autoplay`, `playsinline`, sem controles de registro.
- Saem da Visão geral: o cartão de leitura do momento (já existe no Painel) e as barras "Tudo ligado junto", que vão
  para a página **Sobre**, logo depois de "Como funciona, do começo ao fim". O link para a página Sobre continua, abaixo
  dos pontos.

## 4. Navegação e animação (opção A, aprovada)

- O índice do cenário fica em `st.session_state["vg_cenario"]` (padrão 0).
- **Seta** (`st.button`, ícone `:material/arrow_forward:`, chave `vg_proximo`): índice + 1, voltando ao 1º depois
  do 4º.
- **Pontos**: quatro botões pequenos (chaves `vg_ponto_0..3`); o atual aparece preenchido em verde e desabilitado.
  Texto "N de 4" ao lado.
- **Animação**: o contêiner do cenário recebe uma classe CSS com `@keyframes` (entra deslizando da direita, 24 px,
  com esmaecido, 0,4 s, `ease-out`). Respeita `prefers-reduced-motion` (sem deslize, só troca).
- A simulação é recriada a cada troca e começa do início. Só o cenário aberto é montado.

## 5. Arquivos

| Arquivo | Mudança |
|---|---|
| `src/operador/visao_geral.py` (novo) | `Cenario` (dataclass: `id, verbo, icone, titulo, texto, cena`), `CENARIOS` (os quatro, em ordem), `proximo(i)`, `video_do_cenario(c, pasta) -> Path \| None` (procura `visao_geral_<id>.mp4`) |
| `src/operador/app.py` | `pagina_visao_geral` refeita (cenário atual, vídeo ou espaço reservado, player compacto, seta, pontos); `_barras_sistema()` chamado em `pagina_sobre` |
| `src/operador/estilo.py` | CSS do cenário: grade vídeo/simulação, espaço reservado, seta, pontos, animação |
| `tests/test_visao_geral.py` (novo) | testes rápidos de `visao_geral.py` e de fumaça da página |

Pasta dos vídeos: `data/raw/video/veo3/visao_geral/` (fora do Git, como os outros clipes). O vídeo é copiado para
`src/operador/static/` com o `_estatico` que a interface já usa.

**Altura:** o player (`cruzamento.html_cruzamento`) já se adapta à largura; na coluna da direita ele fica com cerca de
metade da largura e a altura do `components.html` cai de 800 para um valor medido na tela (alvo: cenário inteiro em
768 px de altura). Se não couber, o primeiro ajuste é esconder o rodapé do player nesta página.

## 6. Testes

- `CENARIOS` tem quatro itens, ids únicos, nesta ordem, e cada `cena` existe no exportado da simulação.
- `proximo`: 0 → 1, 3 → 0.
- `video_do_cenario`: arquivo ausente → `None`; presente → o caminho.
- Nenhum texto de cenário tem travessão (—).
- Fumaça com `streamlit.testing` (`AppTest`) logada: a Visão geral abre no cenário 1; clicar na seta mostra o
  cenário 2; com a pasta vazia, aparece o espaço reservado; a página Sobre mostra as barras.
- Conferência visual com o Playwright em 1366 × 768: os quatro cenários sem barra de rolagem vertical.

## 7. Fora do escopo

Gerar ou editar os vídeos (a Tamires gera no Veo 3); mudar a área Câmeras; mudar o **Painel** (fica exatamente
como está, inclusive o cartão de leitura e os cards de prevenção); trocar a simulação; carrossel com os
quatro cenários carregados ao mesmo tempo (opção B, descartada).
