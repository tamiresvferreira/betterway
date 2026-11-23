# Visão na faixa de pedestres — plano de implementação

> **Para quem executa:** superpowers:executing-plans (nativo, nesta sessão). Passos com checkbox (`- [ ]`).

**Objetivo:** detectar, rastrear e medir pedestres, veículos e pessoas com auxílio de mobilidade numa faixa de
pedestres (vídeo público), gerando eventos no banco e evidências com rostos e placas borrados.

**Arquitetura:** `src/visao/visao.py` com funções puras (geometria, travessias, conflitos, PCD, borrão, banco, leitura
de vídeo) testadas com detecções escritas à mão; `src/visao/detector.py` isola o YOLO-World + ByteTrack; o notebook
07 junta tudo e mede.

**Tecnologias:** Python 3.14 (`.venv` na raiz), numpy, opencv-python, ultralytics (YOLO-World `yolov8s-worldv2.pt`,
ByteTrack), torch CPU, sqlite3, pytest.

**Spec:** `docs/specs/2026-11-12-visao-pedestres-design.md`

## Restrições globais

- Não mexer fora de `1TIAO/GLOBAL-SOLUTION-2/`. Português em textos, comentários e commits.
- Constantes de `visao.py` (valores da §6 do spec): `N_CONFIRMA = 3`, `TOLERANCIA_SUMICO_S = 1.0`, `TETO_S = 120`,
  `VEL_IDOSO_MS = 1.2`, `JANELA_CONFLITO_S = 1.0`, `BLOQUEIO_S = 2.0`, `MIN_QUADROS_PCD = 5`,
  `CONF_MIN_AUXILIO = 0.25`, `SOBREPOSICAO_PCD = 0.3`, `DIST_PCD_REL = 0.6`, `FRACAO_CABECA = 0.25`,
  `LIMIAR_BORRAO = 0.25`.
- Classes: `VEICULOS_CONFLITO = {"car", "motorcycle", "bus", "truck"}`; `AUXILIOS = {"wheelchair", "walker", "crutch", "cane"}`;
  `"bicycle"` é contada, não gera conflito; `"license plate"` só é borrada.
- Status de travessia: `concluida`, `retorno`, `nao_concluida`, `inicio_desconhecido`, `acima_do_teto`. Só
  `concluida` entra em médias de duração e velocidade. Flag `abaixo_1_2_ms` quando velocidade < 1,2 m/s.
- Nenhum teste rápido importa ultralytics nem baixa pesos; o teste com modelo real é `@pytest.mark.slow`.
- Nenhuma função grava quadro em disco a não ser `salvar_quadro` (que sempre borra).
- Rodar a partir de `1TIAO/GLOBAL-SOLUTION-2/`: `../../.venv/Scripts/python.exe -m pytest tests -q -m "not slow"`.

## Pontos de atenção (cobertos por testes nas tarefas indicadas)

1. JSON da faixa sem uma chave obrigatória → `ValueError` dizendo qual chave falta (Tarefa 1).
2. Pessoa com `track_id = None` (rastreador perdeu) → ignorada nas travessias, sem erro (Tarefa 2).
3. Duas detecções do mesmo `track_id` no mesmo quadro → contadas como uma (Tarefa 2).
4. Valores numpy (`np.float32`, `np.int64`) no payload → gravados sem erro de serialização JSON (Tarefa 5).
5. Vídeo processado como fluxo (gerador), sem carregar todos os quadros na memória (Tarefa 6).

---

### Tarefa 1: faixa (geometria)

**Arquivos:** criar `src/visao/visao.py`, `tests/test_visao.py`; `tests/conftest.py` passa a incluir `src/visao` no `sys.path`.

**Produz:** `Deteccao` (dataclass do spec §3); `Faixa(poligono: list[tuple[float,float]], resolucao: tuple[int,int], lado_a: tuple[int,int], lado_b: tuple[int,int], comprimento_m: float)` com `Faixa.carregar(caminho) -> Faixa`, `Faixa.de_dict(d) -> Faixa`, `.para_resolucao(largura, altura) -> Faixa`, `.contem(ponto) -> bool`, `.lado_mais_proximo(ponto) -> "A" | "B"`; `ponto_da_pessoa(caixa) -> tuple[float, float]`.

- [ ] **Passo 1: testes que falham** (spec §5, itens 1–5 + ponto de atenção 1), com estes casos literais:
  - `test_trapezio_em_perspectiva`: polígono `[(100,600),(1180,600),(900,300),(380,300)]`; `(640,450)` dentro, `(640,250)` fora, `(150,320)` fora.
  - `test_poligono_concavo`: em "U" `[(0,0),(300,0),(300,300),(200,300),(200,100),(100,100),(100,300),(0,300)]`; `(150,200)` fora (no vão), `(50,200)` e `(250,200)` dentro.
  - `test_sentido_dos_vertices_nao_importa`: o mesmo trapézio invertido dá os mesmos resultados nos três pontos.
  - `test_poligono_invalido`: 2 pontos → `ValueError` com "pelo menos 3"; gravata-borboleta `[(0,0),(100,100),(100,0),(0,100)]` → `ValueError` com "se cruzam".
  - `test_ponto_da_pessoa_e_a_base`: `ponto_da_pessoa((600,200,680,460)) == (640.0, 460.0)`; com o trapézio, essa caixa conta como dentro, embora `(640,200)` esteja fora.
  - `test_borda_conta_como_dentro`: `(640,600)` (sobre o lado de baixo) → dentro.
  - `test_reescala_mesma_proporcao`: faixa de 1280×720 `.para_resolucao(1920,1080)` multiplica os vértices por 1,5; `test_proporcao_diferente_recusa`: `.para_resolucao(1440,1080)` → `ValueError` com "proporção".
  - `test_json_sem_chave`: dict sem `comprimento_m` → `ValueError` citando `comprimento_m`.
- [ ] **Passo 2:** rodar `-k "trapezio or concavo or sentido or invalido or base or borda or reescala or proporcao or json"` → FAIL (ImportError).
- [ ] **Passo 3:** implementar. Ponto no polígono por cruzamento de raio + teste de distância a cada aresta (≤ 1e-6 → dentro); autointerseção por teste de segmentos não adjacentes.
- [ ] **Passo 4:** suíte rápida inteira passa.
- [ ] **Passo 5:** commit `Estudo B: geometria da faixa para o módulo de visão`.

### Tarefa 2: travessias

**Arquivos:** `visao.py`; `tests/test_visao.py`.

**Consome:** `Faixa`, `Deteccao`, `ponto_da_pessoa`. **Produz:** `Travessia` (dataclass: `track_id, quadro_inicio, quadro_fim, duracao_s, velocidade_ms, lado_entrada, lado_saida, status, abaixo_1_2_ms, pcd`) e `travessias(deteccoes: list[Deteccao], faixa: Faixa, fps: float, pcd_ids: set[int] = frozenset()) -> list[Travessia]`.

Helper de teste `trajeto(track_id, pontos_por_quadro)` gera caixas de 40×100 px cuja base cai em cada ponto. Faixa de teste: retângulo `[(0,0),(100,0),(100,1200),(0,1200)]` em 1280×1280, `lado_a` = aresta de cima (y=0), `lado_b` = aresta de baixo (y=1200), `comprimento_m = 12`.

- [ ] **Passo 1: testes que falham** (spec §5, itens 6–14 + pontos de atenção 2 e 3):
  - `test_travessia_simples`: fora (y=-50) 3 quadros, dentro de y=10 a y=1190 em 300 quadros, fora (y=1250) 3 quadros, fps 30 → 1 travessia `concluida`, `duracao_s == pytest.approx(10.0, abs=0.2)`, `velocidade_ms ≈ 1.2`, lados `A`→`B`.
  - `test_tremor_na_borda`: alterna dentro/fora a cada quadro por 20 quadros e depois fica fora → 0 travessias concluídas.
  - `test_oclusao_curta_mantem_uma_travessia`: some 20 quadros (0,67 s) no meio → 1 `concluida`.
  - `test_troca_de_id`: id 1 até o meio, id 2 do meio ao fim → `[nao_concluida, inicio_desconhecido]`, nenhuma com `duracao_s` > duração real.
  - `test_retorno`: entra por A e sai por A → `retorno`.
  - `test_ja_dentro_no_primeiro_quadro`: → `inicio_desconhecido`.
  - `test_fps_muda_a_duracao`: a mesma sequência a 15 fps → 20 s, a 30 fps → 10 s; `test_fps_invalido`: 0, -1 e `None` → `ValueError`.
  - `test_varias_pessoas`: ids 1 e 2 com 300 e 450 quadros → 10 s e 15 s.
  - `test_parado_acima_do_teto`: 130 s dentro e depois sai por B → `acima_do_teto`.
  - `test_abaixo_1_2_ms`: 12 m em 15 s → `velocidade_ms == pytest.approx(0.8, abs=0.02)` e `abaixo_1_2_ms is True`.
  - `test_track_none_e_ignorado`: pessoa com `track_id=None` → nenhuma travessia e nenhum erro.
  - `test_deteccao_duplicada_no_quadro`: duas caixas do id 1 em cada quadro → mesmo resultado de `test_travessia_simples`.
- [ ] **Passo 2:** rodar → FAIL. **Passo 3:** implementar (máquina de estados por `track_id`: fora → entrando (N_CONFIRMA) → dentro → saindo (N_CONFIRMA); sumiço > `TOLERANCIA_SUMICO_S` encerra como `nao_concluida`; o lado é o da aresta mais próxima do ponto no quadro de transição). **Passo 4:** suíte rápida passa. **Passo 5:** commit `Estudo B: travessias com status e velocidade`.

### Tarefa 3: PCD, conflitos e bloqueios

**Arquivos:** `visao.py`; `tests/test_visao.py`.

**Produz:** `associar_auxilios(deteccoes_do_quadro: list[Deteccao]) -> dict[int, str]` (track_id → classe do auxílio); `pessoas_pcd(deteccoes) -> set[int]`; `Conflito` (`quadro, track_veiculo, classe_veiculo, track_pedestre, severidade`) e `conflitos(deteccoes, faixa, fps, pcd_ids) -> list[Conflito]`; `Bloqueio` (`quadro_inicio, quadro_fim, track_veiculo`) e `bloqueios(deteccoes, faixa, fps) -> list[Bloqueio]`; `contagem_bicicletas(deteccoes, faixa) -> int` (ids únicos).

- [ ] **Passo 1: testes que falham** (spec §5, itens 15–25):
  - `test_cadeira_vazia`: só uma `wheelchair` → `associar_auxilios == {}`.
  - `test_acompanhante`: pessoa 1 sobre a cadeira (sobreposição 0,8) e pessoa 2 empurrando (0,35) → `{1: "wheelchair"}`.
  - `test_limiar_relativo_ao_tamanho`: pessoa pequena (20×50) com cadeira pequena colada e pessoa grande (100×250) com cadeira colada → as duas marcadas; a cadeira pequena deslocada 40 px da pessoa pequena (> 0,6 × 50) → não marca.
  - `test_persistencia_pcd`: auxílio colado em 5 quadros → marcada; em 1 quadro → não.
  - `test_confianca_baixa_ignorada`: auxílio com `conf=0.2` → não marca.
  - `test_outros_auxilios` (parametrizado com `walker`, `crutch`, `cane`): colado marca; longe não.
  - `test_conflito_deduplicado`: carro id 7 dentro da faixa por 40 quadros com pedestre dentro → 1 conflito.
  - `test_janela_de_conflito`: pedestre saiu há 30 quadros (1,0 s a 30 fps) → conflito; há 31 quadros → nenhum.
  - `test_classes_de_veiculo` (parametrizado): `car`, `motorcycle`, `bus`, `truck` → conflito; `bicycle` → nenhum conflito e `contagem_bicicletas == 1`.
  - `test_bloqueio`: carro parado 60 quadros (2 s) na faixa vazia → 1 bloqueio e 0 conflitos; 59 quadros → 0 bloqueios.
  - `test_severidade_pcd`: pedestre em `pcd_ids` → `severidade == "alta"`; senão `"normal"`.
- [ ] **Passo 2:** FAIL. **Passo 3:** implementar (sobreposição = interseção ÷ área do auxílio; distância entre centros ≤ `DIST_PCD_REL` × altura da pessoa; conflito único por par veículo × pedestre enquanto ambos estiverem na janela). **Passo 4:** suíte passa. **Passo 5:** commit `Estudo B: PCD, conflitos e bloqueios da faixa`.

### Tarefa 4: privacidade

**Arquivos:** `visao.py`; `tests/test_visao.py`.

**Produz:** `borrar(imagem: np.ndarray, deteccoes_do_quadro: list[Deteccao]) -> np.ndarray` e `salvar_quadro(imagem, deteccoes_do_quadro, caminho: Path) -> Path`.

- [ ] **Passo 1: testes que falham** (spec §5, itens 26–32), imagens sintéticas de ruído aleatório (`np.random.default_rng(0)`, 200×300×3 uint8):
  - `test_todas_as_cabecas`: 3 pessoas → nas 3 regiões de cabeça (quarto superior da caixa) o desvio-padrão cai para ≤ 25% do original.
  - `test_caixa_na_borda`: caixa `(-20,-30,40,80)` e `(280,150,330,260)` → sem erro; a parte dentro da imagem é borrada.
  - `test_sem_pessoas_identica`: `np.array_equal(borrar(img, []), img)`.
  - `test_entrada_intacta`: a cópia de `img` feita antes é igual a `img` depois da chamada.
  - `test_placa_borrada`: `license plate` em `(100,100,160,130)` → região inteira borrada.
  - `test_salvar_quadro_grava_borrado`: `salvar_quadro` em `tmp_path` e `cv2.imread` → cabeça borrada no arquivo lido do disco.
  - `test_nenhuma_outra_funcao_grava_imagem`: o código-fonte de `visao.py` só contém `cv2.imwrite`/`VideoWriter.write` dentro de `salvar_quadro` e `gravar_video_borrado` (inspeção do fonte com `inspect`).
- [ ] **Passo 2:** FAIL. **Passo 3:** implementar (pixelização: reduz a região para 6×6 e amplia com `INTER_NEAREST`; recorta a caixa aos limites da imagem). Inclui `gravar_video_borrado(quadros_e_deteccoes, caminho, fps)` usando `borrar` em cada quadro. **Passo 4:** suíte passa. **Passo 5:** commit `Estudo B: borrão de cabeças e placas antes de salvar`.

### Tarefa 5: eventos no banco

**Arquivos:** `visao.py`; `src/central/schema.sql` (coluna `chave TEXT UNIQUE` em `eventos`); `tests/test_visao.py`.

**Produz:** `migrar(con: sqlite3.Connection) -> None` (acrescenta `chave` e índice único, se faltarem); `Evento` (`tipo, quadro, track_id, valor, payload: dict`); `eventos_de(travessias, conflitos, bloqueios, pcd_ids, deteccoes, faixa, fps) -> list[Evento]`; `gravar_eventos(con, eventos, video_id: str) -> int` (inseridos).

- [ ] **Passo 1: testes que falham** (spec §5, itens 33–38 + ponto de atenção 4), banco em memória criado com `schema.sql`:
  - `test_idempotencia`: gravar a mesma lista duas vezes → contagem igual à da primeira vez.
  - `test_transacao`: lista com um evento inválido no meio (`tipo=None`) → `sqlite3.IntegrityError` e 0 linhas no banco.
  - `test_nao_concluida_entra`: uma travessia `nao_concluida` gera evento com `payload["status"] == "nao_concluida"`.
  - `test_origem_invalida_recusada`: `INSERT` direto com `origem='camera'` → `sqlite3.IntegrityError`.
  - `test_timestamp_iso_sao_paulo`: `timestamp` termina com `-03:00` e passa em `datetime.fromisoformat`.
  - `test_payload_com_numpy`: `valor=np.float32(1.5)`, `payload={"x": np.int64(3)}` → grava sem erro.
  - `test_schema_igual_ao_banco_real`: se `data/processed/seguranca_viaria.db` existir, depois de `migrar` as colunas de `eventos` (nome e tipo) são iguais às do banco em memória; senão, `pytest.skip`.
  - `test_payload_marca_demonstracao`: todo evento gravado tem `"demonstracao": true` e `"video_id"` no payload.
  - `test_tipos_de_evento`: a travessia simples da Tarefa 2 com o id 1 em `pcd_ids` gera ao menos um evento de cada
    tipo `pedestre_na_faixa`, `pcd_na_faixa`, `travessia` e `contagem_minuto`; um conflito gera
    `conflito_veiculo_pedestre` e um bloqueio gera `bloqueio_faixa`.
- [ ] **Passo 2:** FAIL. **Passo 3:** implementar (`chave = f"{video_id}:{quadro}:{track_id}:{tipo}"`; `INSERT OR IGNORE` dentro de `with con:`; `json.dumps(..., default=)` convertendo tipos numpy). **Passo 4:** suíte passa. **Passo 5:** commit `Estudo B: eventos da visão no banco, idempotentes`.

### Tarefa 6: leitura de vídeo, detector e ambiente

**Arquivos:** `visao.py` (`ler_video`); criar `src/visao/detector.py`; `requirements.txt` (`ultralytics`, `opencv-python`); `tests/test_visao.py`; `pytest.ini` em `1TIAO/GLOBAL-SOLUTION-2/` registrando o marcador `slow`.

**Produz:** `ler_video(caminho) -> tuple[float, int, int, Iterator[np.ndarray]]`; `detector.detectar(caminho_video, classes: list[str], a_cada: int = 1) -> Iterator[tuple[int, np.ndarray, list[Deteccao]]]` (YOLO-World `yolov8s-worldv2.pt`, `model.set_classes(classes)`, `model.track(persist=True, tracker="bytetrack.yaml")`).

- [ ] **Passo 0:** instalar `torch` (CPU) e `ultralytics` em segundo plano no começo da execução (é lento no OneDrive).
- [ ] **Passo 1: testes que falham** (spec §5, itens 39–41):
  - `test_video_inexistente`: `FileNotFoundError`.
  - `test_video_vazio`: arquivo de 0 bytes em `tmp_path` → `ValueError` com "vídeo".
  - `test_video_corrompido`: arquivo com bytes aleatórios e extensão `.mp4` → `ValueError`.
  - `test_video_sintetico_e_gerador`: vídeo de 10 quadros 64×48 gravado com `cv2.VideoWriter` em `tmp_path` → `fps == 10`, dimensões certas, o retorno é um gerador (`inspect.isgenerator`) com 10 quadros.
  - `test_quadro_sem_deteccao`: `travessias([], faixa, 30) == []` e `borrar(img, [])` idêntica.
  - `test_fumaca_modelo_real` (`@pytest.mark.slow`): `detectar` em 30 quadros do vídeo real devolve `Deteccao` com classes do conjunto pedido.
- [ ] **Passo 2:** FAIL. **Passo 3:** implementar. **Passo 4:** suíte rápida passa; rodar `-m slow` uma vez depois do vídeo baixado (Tarefa 7). **Passo 5:** commit `Estudo B: leitura de vídeo e detector YOLO-World`.

### Tarefa 7: dados (vídeo, faixa e conjunto de avaliação)

**Arquivos:** `data/raw/video/FONTE.md` (no Git; o vídeo, fora); `src/visao/faixa_<nome>.json`; `data/avaliacao_pcd/` (imagens + `rotulos.csv` + `FONTES.csv`); `.gitignore` da GS ganha exceção só para `data/raw/video/FONTE.md`.

- [ ] **Passo 1:** escolher um vídeo de faixa de pedestre vista do alto, com licença livre (Pexels, Pixabay ou Wikimedia Commons), preferência por cena brasileira; registrar URL, autor e licença em `FONTE.md`.
- [ ] **Passo 2:** extrair o primeiro quadro, conferir visualmente e escrever o JSON da faixa (polígono, `lado_a`, `lado_b`, `comprimento_m` estimado pelo nº de faixas de rolamento × 3,5 m, resolução); validar com `Faixa.carregar`.
- [ ] **Passo 3:** montar ~40–60 imagens de rua com licença livre (Wikimedia Commons): cadeira de rodas, andador, muleta, bengala e negativos só com pedestres; `rotulos.csv` com rótulo **por imagem** (quais auxílios aparecem) e `FONTES.csv` com licença e autor.
- [ ] **Passo 4:** commit `Estudo B: vídeo, faixa e conjunto de avaliação de PCD (fontes e licenças)`.

### Tarefa 8: notebook 07, métricas e evidências

**Arquivos:** criar `src/visao/07_visao_pedestres.ipynb` (gerado por script no scratchpad, como os anteriores); `src/visao/README.md`; evidências `docs/evidencias/estudo_b/07_*`.

**Consome:** tudo acima.

Seções (markdown de decisão + "Leitura" depois de cada resultado; cores `#2a78d6` / `#eb6834`): 1. configuração e fonte do vídeo; 2. detecção + rastreamento (`a_cada` ajustado para caber em CPU) e fps de processamento; 3. travessias (tabela por status, distribuição de duração e velocidade, % abaixo de 1,2 m/s); 4. PCD, conflitos e bloqueios por hora; 5. conferência visual de ~30 quadros sorteados (precisão e recall aproximados de pessoa e veículo, preenchidos depois de eu ver os quadros); 6. avaliação de PCD no conjunto de imagens (precisão e recall por classe, por imagem, e falso alarme nos negativos, em função de `CONF_MIN_AUXILIO`); 7. eventos gravados (`migrar` + `gravar_eventos`, consulta de conferência); 8. evidências (PNGs com `salvar_quadro`, GIF curto, `07_metricas.csv`); 9. limitações.

- [ ] **Passo 1:** gerar e rodar o notebook (`nbconvert --execute`) → termina sem erro.
- [ ] **Passo 2:** conferir os quadros sorteados e as detecções nas imagens de avaliação, e escrever as leituras com os números.
- [ ] **Passo 3:** rodar a suíte rápida e a lenta; salvar a saída em `docs/evidencias/estudo_b/07_testes_visao.txt`.
- [ ] **Passo 4:** `src/visao/README.md` (como rodar, fontes, decisões, limitações) e commit `Estudo B: notebook 07 de visão na faixa, métricas e evidências`.
