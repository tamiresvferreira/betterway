# Modelo de risco de ocorrência — plano de implementação

> **Para quem executa:** usar superpowers:executing-plans (nativo, nesta sessão). Passos com checkbox (`- [ ]`).

**Objetivo:** prever a taxa de atropelamentos por célula de ~500 m × hora × tipo de dia × chuva e expor isso na
`risco()` como protagonista, mantendo a gravidade (notebook 05) como coadjuvante.

**Arquitetura:** funções puras de agregação/exposição/variáveis em `risco.py` (usadas pelo notebook e pela função);
notebook 06 treina linha de base, Poisson (statsmodels) e gradient boosting Poisson (scikit-learn) e salva
`models/modelo_risco.joblib`; `risco()` carrega os dois modelos em cache.

**Tecnologias:** Python 3.14 (`.venv` na raiz), pandas, numpy, statsmodels, scikit-learn, joblib, pytest, nbformat/nbconvert.

**Spec:** `docs/specs/2026-11-11-modelo-risco-design.md`

## Restrições globais

- Não mexer fora de `1TIAO/GLOBAL-SOLUTION-2/`. Textos, comentários e commits em português.
- Célula = `floor(lat/0.005), floor(lon/0.005)` (função existente `_celula`, tornada pública como `celula`).
- Chovendo = `chuva_mm >= 0.2` (`LIMIAR_CHUVA_MM`). Chuva da hora H = valor do Open-Meteo marcado em H+1.
- Treino 2022–2023, teste 2024, checagem 2025. Excluir registros sem hora ou sem coordenada válida.
- Combinação = hora (0–23) × fim_de_semana (0/1) × chovendo (0/1) = 96 por célula; células = as com ≥ 1 atropelamento válido em 2022–2025.
- Regra de escolha: menor deviance de Poisson média em `GroupKFold(5)` por célula; diferença < 1% → Poisson.
- Critério de "bom": D² > 0 contra a base; top 5% de células concentra mais atropelamentos de 2024 que o ranking histórico; erro do total de 2024 ≤ 10%.
- Níveis: cortes = quantis 50% e 90% de λ no teste 2024, ponderados pela exposição.
- Motivo "chuva" só se o limite inferior do IC 95% da razão de taxas da chuva (Poisson) for > 1.
- Rodar a partir de `1TIAO/GLOBAL-SOLUTION-2/`: `../../.venv/Scripts/python.exe -m pytest tests -v`.

## Pontos de atenção (cobertos por testes nas tarefas indicadas)

1. Última hora da série (31/12/2025 23h) não tem o valor da hora seguinte → a exposição ignora essa hora, sem erro (Tarefa 1).
2. Domingo 23h e segunda 0h caem em tipos de dia diferentes (fim de semana × útil) (Tarefa 1).
3. `quando` com fuso (datetime aware) é aceito e usa a hora local informada (Tarefa 4).
4. `chuva_mm` muito alta (ex.: 300) não quebra e as probabilidades ficam em [0, 1] (Tarefa 4).
5. Célula sem histórico recebe variáveis zeradas, nunca erro (Tarefa 2).

---

### Tarefa 1: exposição e contagens agregadas

**Arquivos:** modificar `src/estudo_b_risco_vida/risco.py`; testes em `tests/test_risco_ocorrencia.py` (novo).

**Interfaces (produz):**
- `celula(lat, lon) -> list[tuple[int, int]]` (renomear `_celula`; manter `_celula = celula` para o código existente).
- `chuva_por_hora(serie: pd.Series) -> pd.Series` — recebe a série do Open-Meteo (índice = carimbo, valor = mm) e devolve índice = início da hora (carimbo − 1 h).
- `exposicao(chuva_hora: pd.Series, inicio: str, fim: str) -> pd.DataFrame` com colunas `hora, fim_de_semana, chovendo, horas` (só combinações que ocorreram; `inicio`/`fim` inclusivos, datas `AAAA-MM-DD`).
- `contagens(eventos: pd.DataFrame) -> pd.DataFrame` — `eventos` tem `latitude, longitude, quando, chuva_mm`; devolve `celula, hora, fim_de_semana, chovendo, n`.

- [ ] **Passo 1: testes que falham**

```python
def test_chuva_por_hora_desloca_uma_hora():
    s = pd.Series([0.0, 1.5], index=pd.to_datetime(["2024-01-01 01:00", "2024-01-01 02:00"]))
    h = rv.chuva_por_hora(s)
    assert h.index.tolist() == list(pd.to_datetime(["2024-01-01 00:00", "2024-01-01 01:00"]))
    assert h.tolist() == [0.0, 1.5]

def test_exposicao_conta_horas_por_combinacao():
    # sábado 06/01/2024 23h (fds, seco), domingo 07/01 23h (fds, chuva 0,5), segunda 08/01 0h (útil, seco)
    idx = pd.to_datetime(["2024-01-06 23:00", "2024-01-07 23:00", "2024-01-08 00:00"])
    e = rv.exposicao(pd.Series([0.0, 0.5, 0.1], index=idx), "2024-01-06", "2024-01-08")
    e = e.set_index(["hora", "fim_de_semana", "chovendo"])["horas"].to_dict()
    assert e == {(23, 1, 0): 1, (23, 1, 1): 1, (0, 0, 0): 1}

def test_exposicao_ignora_horas_sem_valor_de_chuva():
    idx = pd.to_datetime(["2024-01-08 10:00"])  # 11h não tem valor
    e = rv.exposicao(pd.Series([0.0], index=idx), "2024-01-08", "2024-01-08")
    assert e["horas"].sum() == 1

def test_contagens_agrupa_por_celula_e_combinacao():
    ev = pd.DataFrame({"latitude": [-23.551, -23.551, -23.551, -23.701],
                       "longitude": [-46.631, -46.631, -46.631, -46.701],
                       "quando": pd.to_datetime(["2024-01-08 18:10", "2024-01-09 18:50", "2024-01-13 18:00", "2024-01-08 03:00"]),
                       "chuva_mm": [0.0, 0.0, 0.0, 2.0]})
    c = rv.contagens(ev).set_index(["celula", "hora", "fim_de_semana", "chovendo"])["n"].to_dict()
    # -23.551/0.005 = -4710.2 → -4711 ; -46.631/0.005 = -9326.2 → -9327 ; -23.701 → -4741 ; -46.701 → -9341
    assert c == {((-4711, -9327), 18, 0, 0): 2, ((-4711, -9327), 18, 1, 0): 1, ((-4741, -9341), 3, 0, 1): 1}
```

- [ ] **Passo 2:** rodar `-k "chuva_por_hora or exposicao or contagens"` → FAIL (`AttributeError`).
- [ ] **Passo 3:** implementar as quatro funções. `exposicao`: filtrar `inicio <= índice < fim + 1 dia`; agrupar por `hour`, `day_of_week >= 5`, `valor >= LIMIAR_CHUVA_MM`.
- [ ] **Passo 4:** rodar a suíte inteira → todos passam (15 antigos + 4 novos).
- [ ] **Passo 5:** commit `Estudo B: exposição e contagens para o modelo de risco`.

### Tarefa 2: variáveis por célula e montagem das variáveis do risco

**Arquivos:** `risco.py`; `tests/test_risco_ocorrencia.py`.

**Interfaces:**
- Consome: `construir_tabelas` (existente; DBSCAN só com o treino), `celula`.
- Produz:
  - `RISCO_VARIAVEIS = ["hora_sin", "hora_cos", "hora_sin2", "hora_cos2", "fim_de_semana", "chovendo", "hist_log", "em_grupo", "peso_grupo", "rodovia"]` (2º harmônico da hora para os dois picos do dia).
  - `variaveis_celula(tabelas: dict) -> pd.DataFrame` indexado por `celula`, colunas `hist_log` (= log1p(n de treino)), `em_grupo` (0/1: algum ponto de treino da célula está em grupo), `peso_grupo` (maior peso de grupo com ponto na célula; 0 se nenhum), `rodovia` (0/1: maioria dos pontos de treino da célula em rodovia).
  - `montar_variaveis_risco(celulas: list, hora, fim_de_semana, chovendo, tab_celula: pd.DataFrame) -> pd.DataFrame` com as colunas de `RISCO_VARIAVEIS` na ordem; célula ausente de `tab_celula` → `hist_log = em_grupo = peso_grupo = rodovia = 0`.

- [ ] **Passo 1: testes que falham** (reusar a fixture `treino_sintetico` — mover para `tests/conftest.py`)

```python
def test_variaveis_celula_resume_o_treino(treino_sintetico):
    tc = rv.variaveis_celula(rv.construir_tabelas(treino_sintetico, eps_m=100, min_samples=8))
    a, b = rv.celula([-23.55], [-46.63])[0], rv.celula([-23.70], [-46.70])[0]
    assert tc.loc[a].tolist() == pytest.approx([math.log1p(10), 1, 14, 0])
    assert tc.loc[b].tolist() == pytest.approx([math.log1p(1), 0, 0, 1])

def test_celula_sem_historico_recebe_zeros(treino_sintetico):
    tc = rv.variaveis_celula(rv.construir_tabelas(treino_sintetico, eps_m=100, min_samples=8))
    v = rv.montar_variaveis_risco([(0, 0)], [18], [0], [1], tc)
    assert v[["hist_log", "em_grupo", "peso_grupo", "rodovia"]].iloc[0].tolist() == [0, 0, 0, 0]
    assert v.columns.tolist() == rv.RISCO_VARIAVEIS
    assert v["hora_sin"].iloc[0] == pytest.approx(-1.0) and v["hora_cos2"].iloc[0] == pytest.approx(-1.0)  # 18h: 2·270° = 540°
```

- [ ] **Passo 2:** rodar → FAIL.
- [ ] **Passo 3:** implementar as duas funções (hora_sin2/cos2 = sin/cos(4π·hora/24)).
- [ ] **Passo 4:** suíte inteira passa.
- [ ] **Passo 5:** commit `Estudo B: variáveis por célula para o modelo de risco`.

### Tarefa 3: notebook 06 — treino, métricas e modelo salvo

**Arquivos:** criar `src/estudo_b_risco_vida/06_modelo_risco_ocorrencia.ipynb` (gerado por script no scratchpad, como os anteriores); saída `models/modelo_risco.joblib`; evidências `docs/evidencias/estudo_b/06_*.png`.

**Interfaces:**
- Consome: Tarefas 1–2; `data/processed/atropelamentos_sp_2022_2025.parquet`; `data/raw/open_meteo_precipitacao_sp_2022_2025.csv`.
- Produz o pacote joblib (dict) com chaves: `modelo` (objeto com `.predict(X) -> taxa por hora`; para a Poisson, um invólucro que aplica `exp(Xβ)`), `nome_modelo`, `variaveis` (= `RISCO_VARIAVEIS`), `tab_celula`, `lambda_media` (float, λ médio do teste ponderado pela exposição), `cortes_nivel` (`{"medio": float, "alto": float}`), `chuva_rr` (`{"rr", "ic_inf", "ic_sup"}` da Poisson), `metricas_teste` (dict), `horas_pico` (lista de horas com maior taxa média; as 2 maiores do perfil de dia útil).

Seções do notebook (markdown de decisão + "Leitura" após cada resultado, cores azul `#2a78d6` / laranja `#eb6834`):
1. Configuração (`achar_raiz`, import de `risco`).
2. Dados: eventos válidos, chuva por hora, exposição de treino/teste/2025; taxa da cidade por hora chuvosa × seca (com IC). Leitura.
3. Painel: células × 96 combinações, `n` (0 quando não houve), `horas`, variáveis de treino. Tamanho e % de zeros.
4. Modelos: linha de base (taxa da célula no treino × perfil hora × tipo de dia); Poisson statsmodels com `offset = log(horas)` (tabela de razões de taxa com IC); HGB `loss="poisson"`, alvo = `n/horas`, `sample_weight = horas`, grade `learning_rate ∈ {0.05, 0.1}`, `max_leaf_nodes ∈ {15, 31}`, `min_samples_leaf ∈ {50, 200}`, `GroupKFold(5)` por célula; deviance de CV das três. Escolha pela regra. Leitura.
5. Teste 2024: D², taxa de acerto e PAI no top 1%/5% de células (contra ranking histórico), ROC-AUC/PR-AUC de `n > 0` usando `λ·horas`, calibração por decil e total. Tabela de critérios (passou/não passou). Gráficos: curva de captura (% de células × % de atropelamentos) e calibração. 2025 como checagem. Leitura.
6. Níveis e pacote: cortes ponderados, salvar joblib (`compress=3`). Leitura + limitações.

- [ ] **Passo 1:** gerar o notebook e rodar `jupyter nbconvert --to notebook --execute --inplace` → termina sem erro.
- [ ] **Passo 2:** conferir que imprime a tabela de critérios e que `models/modelo_risco.joblib` existe.
- [ ] **Passo 3:** escrever as leituras com os números obtidos (sem marcadores pendentes) e rodar de novo.
- [ ] **Passo 4:** commit `Estudo B: modelo de risco de ocorrência (notebook 06)`.

### Tarefa 4: `risco()` com risco de ocorrência

**Arquivos:** `risco.py`; `tests/test_risco_ocorrencia.py`.

**Interfaces:**
- Consome: pacote da Tarefa 3; `_pacote()` existente (gravidade).
- Produz: `risco()` devolve também `probabilidade_atropelamento_1h` (= 1 − e^(−λ)), `risco_relativo` (= λ / `lambda_media`, 2 casas), `probabilidade_atropelamento_fatal_1h` (= produto, 4 casas); `nivel` passa a vir de λ e `cortes_nivel`. Novo `_pacote_risco()` com `lru_cache`, caminho `models/modelo_risco.joblib`. `quando` aware: usar `quando.hour` e `quando.weekday()` como estão (hora local informada). Motivo "horário de pico" quando `quando.hour in horas_pico`; "chuva" só se `chuva_rr["ic_inf"] > 1`.

- [ ] **Passo 1: testes que falham**

```python
LARGO = (-23.54231, -46.61655)

def test_largo_devolve_probabilidade_de_atropelamento_valida():
    r = rv.risco(*LARGO, datetime(2026, 11, 10, 18, 30), 0.0)
    assert 0.0 < r["probabilidade_atropelamento_1h"] < 1.0
    assert r["nivel"] in {"baixo", "medio", "alto"}
    assert r["probabilidade_atropelamento_fatal_1h"] == pytest.approx(
        r["probabilidade_atropelamento_1h"] * r["probabilidade_fatal"], abs=1e-3)

def test_dia_util_18h_tem_mais_risco_que_4h():
    a = rv.risco(*LARGO, datetime(2026, 11, 10, 18, 0), 0.0)
    b = rv.risco(*LARGO, datetime(2026, 11, 10, 4, 0), 0.0)
    assert a["probabilidade_atropelamento_1h"] > b["probabilidade_atropelamento_1h"]

def test_largo_tem_mais_risco_que_celula_sem_historico():
    a = rv.risco(*LARGO, datetime(2026, 11, 10, 18, 0), 0.0)
    b = rv.risco(-23.98, -46.80, datetime(2026, 11, 10, 18, 0), 0.0)   # extremo sul, sem histórico
    assert a["probabilidade_atropelamento_1h"] > b["probabilidade_atropelamento_1h"]

def test_fora_de_sp_tem_risco_baixo_sem_grupo():
    r = rv.risco(-22.90, -43.20, datetime(2026, 11, 10, 18, 0), 0.0)
    assert r["cluster_id"] is None and 0.0 <= r["probabilidade_atropelamento_1h"] < 1.0

def test_quando_com_fuso_e_aceito():
    from zoneinfo import ZoneInfo
    r = rv.risco(*LARGO, datetime(2026, 11, 10, 18, 0, tzinfo=ZoneInfo("America/Sao_Paulo")), 0.0)
    assert 0.0 < r["probabilidade_atropelamento_1h"] < 1.0

def test_chuva_muito_alta_nao_quebra():
    r = rv.risco(*LARGO, datetime(2026, 11, 10, 18, 0), 300.0)
    assert 0.0 <= r["probabilidade_atropelamento_1h"] <= 1.0 and 0.0 <= r["probabilidade_fatal"] <= 1.0
```

- [ ] **Passo 2:** rodar → FAIL (chave ausente).
- [ ] **Passo 3:** implementar (os testes antigos continuam; nenhum depende de o `nivel` vir da gravidade).
- [ ] **Passo 4:** suíte inteira passa; salvar a saída em `docs/evidencias/estudo_b/06_testes_risco.txt`.
- [ ] **Passo 5:** atualizar `src/estudo_b_risco_vida/README.md` (linha do notebook 06, exemplo da saída nova, achado 6) e commit `Estudo B: risco() com risco de ocorrência como protagonista`.
