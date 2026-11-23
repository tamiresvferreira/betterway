# Spec: visão computacional na faixa de pedestres (Estudo B)

Data: 12/11/2026 · Prazo: sábado 14/11 · Status: desenho aprovado em conversa (partes 1 e 2 + requisitos de teste
da usuária); decisões da seção 6 aguardando revisão.

## 1. Objetivo

Detectar e **rastrear** pedestres, veículos e pessoas com cadeira de rodas, andador, muleta ou bengala numa faixa de
pedestres, num vídeo público com licença livre, para:
- acionar os modos do nó (`pedestre_na_faixa`, `pcd_na_faixa`);
- medir o **tempo de travessia** e a velocidade, e comparar com os 1,2 m/s que os semáforos de SP supõem (Duim et
  al., 2017: 97,8% dos idosos andam mais devagar);
- contar **conflitos** veículo × pedestre (quase-acidentes, como em Bellevue) e bloqueios da faixa.

Nada de reconhecimento facial. Todo quadro salvo em disco tem cabeças e placas borradas. O banco guarda só números
e tempos.

**Agora (opção B):** YOLO-World (vocabulário aberto, sem treino) + rastreamento ByteTrack (Ultralytics).
**Depois, se sobrar tempo:** ajuste fino no Google Colab com **imagens** (datasets públicos e imagens com licença
livre, rostos borrados), comparado ao YOLO-World no mesmo conjunto de avaliação. Fora deste spec.

## 2. Componentes e arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/visao/visao.py` | Funções puras e testáveis: geometria da faixa, travessias, conflitos, associação de PCD, borrão, eventos no banco, leitura de vídeo. Não importa o Ultralytics no nível do módulo |
| `src/visao/detector.py` | Única peça que chama o YOLO-World + ByteTrack e converte o resultado em `Deteccao` (ver §3). Os testes rápidos não a usam |
| `src/visao/faixa_<nome>.json` | Configuração da faixa do vídeo: resolução de referência, polígono, bordas de calçada A e B (pares de índices de vértices), comprimento real em metros e fps esperado |
| `src/visao/07_visao_pedestres.ipynb` | Roda o pipeline no vídeo, gera o vídeo de saída borrado, grava eventos e mostra as métricas |
| `tests/test_visao.py` | Testes rápidos com detecções escritas à mão; um teste de fumaça com o modelo real, marcado `@pytest.mark.slow` |
| `data/raw/video/` | Vídeo original (fora do Git) + `FONTE.md` com URL, autor e licença (no Git) |
| `data/avaliacao_pcd/` | ~40–60 imagens de rua com licença livre (cadeira de rodas, andador, muleta, bengala e negativos só com pedestres), anotações e `FONTES.csv` com a licença de cada imagem |
| `docs/evidencias/estudo_b/07_*` | Quadros PNG borrados, GIF curto, tabela de métricas (CSV) e saída do pytest |
| `src/central/schema.sql` | Tabela `eventos` ganha a coluna `chave TEXT UNIQUE` |

## 3. Interfaces principais

```python
@dataclass(frozen=True)
class Deteccao:
    quadro: int            # índice do quadro (0, 1, 2, ...)
    classe: str            # "person", "car", "motorcycle", "bus", "truck", "bicycle", "wheelchair", "walker",
                           # "crutch", "cane", "license plate"
    caixa: tuple[float, float, float, float]   # x1, y1, x2, y2 em pixels
    conf: float
    track_id: int | None   # None para classes não rastreadas
```

- `Faixa.carregar(caminho_json) -> Faixa` e `Faixa.para_resolucao(largura, altura) -> Faixa`.
- `Faixa.contem(ponto) -> bool` e `ponto_da_pessoa(caixa) -> (x, y)` (base da caixa = pés).
- `travessias(deteccoes, faixa, fps) -> list[Travessia]` (`Travessia`: track_id, quadro_inicio, quadro_fim,
  duracao_s, velocidade_ms, lado_entrada, lado_saida, status, pcd).
- `conflitos(deteccoes, faixa, fps, pcd_ids) -> list[Conflito]` e `bloqueios(...) -> list[Bloqueio]`.
- `pessoas_pcd(deteccoes) -> set[int]` (track_ids marcados).
- `borrar(imagem, deteccoes_do_quadro) -> imagem` (devolve cópia) e `salvar_quadro(imagem, deteccoes, caminho)`, a
  única função que grava quadro em disco (sempre borra antes).
- `migrar(con)` e `gravar_eventos(con, eventos, video_id)` (transação única, idempotente).
- `ler_video(caminho) -> (fps, largura, altura, gerador de quadros)`.

## 4. Fluxo

vídeo → `ler_video` → `detector` (YOLO-World + ByteTrack) → lista de `Deteccao` → `Faixa.para_resolucao` →
`pessoas_pcd`, `travessias`, `conflitos`, `bloqueios` → eventos → `gravar_eventos` (tabela `eventos`,
`origem = 'yolo'`, `cluster_id` nulo, `payload_json` com `"demonstracao": true` e a fonte do vídeo) → vídeo de saída
e quadros via `salvar_quadro` (borrados).

Tipos de evento: `pedestre_na_faixa`, `pcd_na_faixa`, `travessia` (com status), `conflito_veiculo_pedestre` (com
severidade), `bloqueio_faixa`, `contagem_minuto`.

## 5. Testes (requisitos da usuária, todos com detecções escritas à mão)

**Região da faixa**
1. Polígono em perspectiva (trapézio) e polígono de 4–6 vértices **côncavo**: pontos dentro e fora corretos.
2. Mesmo resultado com vértices em sentido horário e anti-horário.
3. Menos de 3 pontos ou lados que se cruzam → `ValueError` com mensagem clara.
4. O ponto da pessoa é a base da caixa: pés na faixa e cabeça fora do polígono contam como dentro.
5. Polígono de 1280×720 aplicado a vídeo 1920×1080 é reescalado; proporção diferente (ex.: 1280×720 → 1440×1080) →
   `ValueError`.

**Travessia**
6. Tremor na borda: alternar dentro/fora não vira várias travessias (confirmação por `N_CONFIRMA` quadros seguidos).
7. Oclusão: sumir por até `TOLERANCIA_SUMICO_S` com o mesmo ID → uma travessia só.
8. Troca de ID no meio da faixa → duas travessias com status `nao_concluida` (motivo `id_perdido` / `inicio_desconhecido`),
   nenhuma duração absurda, nenhuma na média.
9. Entra e volta pelo mesmo lado → status `retorno`.
10. Já dentro no primeiro quadro → status `inicio_desconhecido`, fora da média.
11. A mesma sequência a 15 e a 30 fps → durações diferentes e corretas; fps 0, negativo ou ausente → `ValueError`.
12. Várias pessoas ao mesmo tempo → durações independentes.
13. Pessoa parada mais que `TETO_S` → registro válido com status `acima_do_teto`, fora da média.
14. Velocidade: comprimento conhecido da faixa ÷ duração (ex.: 12 m em 10 s = 1,2 m/s); travessia abaixo de 1,2 m/s é
    marcada `abaixo_1_2_ms`.

**Conflito**
15. Mesmo veículo 40 quadros dentro com pedestre → 1 conflito.
16. Janela: pedestre que saiu há `JANELA_CONFLITO_S` ainda conta; um quadro depois, não.
17. Carro, moto, ônibus e caminhão geram conflito; bicicleta não (decisão na §6).
18. Veículo parado ≥ `BLOQUEIO_S` na faixa vazia → 1 `bloqueio_faixa`, nenhum conflito.
19. Conflito com pessoa PCD → severidade `alta`; comum → `normal`.

**PCD**
20. Cadeira vazia (ninguém perto) → nenhuma pessoa marcada, nenhuma pessoa criada.
21. Acompanhante: duas pessoas perto da cadeira → só a de maior sobreposição é marcada.
22. Limiar relativo ao tamanho da caixa: pessoa pequena (longe) e grande (perto) marcadas com a mesma regra.
23. Persistência: marcada a travessia toda se o auxílio aparece em ≥ `MIN_QUADROS_PCD` quadros; detecção isolada não
    marca.
24. Confiança abaixo de `CONF_MIN_AUXILIO` é ignorada.
25. Colado/longe repetido para andador, muleta e bengala.

**Privacidade**
26. Várias pessoas → todas as cabeças borradas.
27. Caixa cortada pela borda da imagem → sem erro de índice.
28. Sem pessoas → imagem idêntica.
29. A entrada não é alterada (devolve cópia).
30. Borrão forte: desvio-padrão dos pixels na região da cabeça cai abaixo de `LIMIAR_BORRAO`.
31. `salvar_quadro` grava o arquivo já borrado (o teste relê o arquivo do disco), e é a única função que grava quadros.
32. Placas (`license plate`) também borradas (decisão na §6).

**Banco**
33. Idempotência: processar o mesmo vídeo duas vezes não duplica eventos (`chave` = vídeo + quadro + track + tipo).
34. Transação: erro no meio → nenhum evento do lote fica no banco.
35. Travessia não concluída entra no banco com o status.
36. `origem` fora dos valores previstos e campos obrigatórios nulos → erro do banco (CHECK / NOT NULL).
37. `timestamp` em ISO com o fuso de São Paulo (`-03:00`).
38. Mesmo schema: as colunas de `eventos` no banco real (depois de `migrar`) são iguais às do banco em memória criado com
    `schema.sql`.

**Robustez**
39. Vídeo inexistente → `FileNotFoundError`; vazio ou corrompido → `ValueError` claro.
40. Quadro sem nenhuma detecção → segue normalmente.
41. Teste de fumaça com o YOLO-World real, marcado `@pytest.mark.slow` (fora da suíte rápida).

## 6. Decisões (valores iniciais, ajustáveis)

| Decisão | Valor | Por quê |
|---|---|---|
| Ponto da pessoa | centro da base da caixa | os pés tocam a faixa; a cabeça sai do polígono por causa da perspectiva |
| Ponto na borda do polígono | conta como dentro | evita "piscar" na linha; o tremor é tratado pela confirmação |
| `N_CONFIRMA` | 3 quadros seguidos | ~0,1 s a 30 fps: filtra tremor sem atrasar a detecção |
| `TOLERANCIA_SUMICO_S` | 1,0 s | uma oclusão por veículo dura menos que isso; acima, a travessia termina `nao_concluida` |
| Troca de ID | encerra a anterior (`nao_concluida`, `id_perdido`) e abre a nova (`inicio_desconhecido`) | sem como provar que é a mesma pessoa; nenhuma das duas entra na média |
| `TETO_S` | 120 s | acima disso não é travessia típica (parado, ambulante); fica registrado, fora da média |
| Velocidade | `comprimento_m` (da configuração) ÷ duração | evita calibração pixel→metro; o comprimento vem da largura das faixas no vídeo (aprox. 3,5 m por faixa), declarado como estimativa |
| `JANELA_CONFLITO_S` | 1,0 s | pedestre que acabou de sair ainda está na zona de risco |
| Bicicleta | não gera conflito; é contada à parte | o risco de morte do pedestre vem dos motorizados; ciclista pode estar na faixa legitimamente |
| `BLOQUEIO_S` | 2,0 s | veículo parado sobre a faixa obriga o pedestre a desviar |
| Associação de PCD | interseção ÷ área da caixa do auxílio ≥ 0,3 **e** distância entre centros ≤ 0,6 × altura da pessoa | relativo ao tamanho, vale perto e longe |
| `MIN_QUADROS_PCD` | 5 quadros | uma detecção isolada não basta |
| `CONF_MIN_AUXILIO` | 0,25 | o YOLO-World dá confiança mais baixa para classes raras; o valor é calibrado no conjunto de avaliação |
| Borrão | quarto superior da caixa da pessoa (cabeça), pixelização forte | não depende de detector de rosto; funciona de costas e de lado |
| `LIMIAR_BORRAO` | desvio-padrão ≤ 25% do original na região | garante que não é um desfoque leve |
| Placas de veículos | **borradas** (classe `license plate` do YOLO-World) | placa é dado pessoal ligado ao dono; limitação declarada: placas pequenas podem não ser detectadas |
| Chave única do evento | `video_id:quadro:track_id:tipo` | idempotência |
| Horário dos eventos | ISO com `-03:00` (São Paulo) | o vídeo não é ao vivo: o horário é o do processamento, e o quadro vai no `payload_json` |

## 7. Métricas e critério de pronto

| O quê | Como |
|---|---|
| Pessoa e veículo no vídeo | ~30 quadros sorteados e conferidos visualmente: acertos, falsos alarmes e perdas → precisão e recall aproximados |
| Cadeira de rodas, andador, muleta, bengala | precisão e recall no conjunto de avaliação; taxa de falso alarme nas imagens só com pedestres |
| Travessia | distribuição das durações e velocidades; % abaixo de 1,2 m/s |
| Conflitos e bloqueios | por hora de vídeo |
| Velocidade de processamento | quadros por segundo em CPU |

**Pronto quando:** a suíte rápida passa; o notebook 07 roda do início ao fim; o vídeo de saída tem cabeças e placas
borradas; os eventos estão no banco; e a tabela de métricas está em `docs/evidencias/estudo_b/`.

## 8. Fora do escopo

- Ajuste fino no Colab (etapa posterior, se sobrar tempo).
- Integração ao vivo com a central e o ESP32 (dia 17): aqui os eventos só vão para o banco.
- Vídeo do Largo da Concórdia (não há filmagem pública com licença); tudo é marcado como demonstração.
