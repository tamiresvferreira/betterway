# Spec: modelo de risco de ocorrência de atropelamento (Estudo B)

Data: 11/11/2026 · Prazo de implementação: 12/11/2026 à noite (3–4 h) · Status: aprovado em conversa, aguardando revisão do arquivo

## 1. Por que

O módulo 2 do projeto ("Inteligência de risco") precisa dizer **onde e quando um atropelamento é mais provável**,
para o nó agir **antes** (ação preventiva). A primeira versão (notebook 05) modelou só a **gravidade** (dado que houve
atropelamento, ele é fatal?) e ficou fraca (ROC-AUC 0,62), porque não pode usar dados da vítima.

Decisão (11/11/2026): o **risco de ocorrência** passa a ser o protagonista; a **gravidade** continua como
coadjuvante, para estimar impacto (atropelamentos e mortes que um sistema integrado poderia evitar).

Base científica: Qiu e Nixon (2008, ref. 15 da bibliografia) estudam chuva × **frequência** de sinistros, que é o que
este modelo mede; Iranitalab e Khattak (2017, ref. 14) seguem como referência da gravidade.

## 2. Unidade, alvo e dados

- **Unidade:** célula de ~500 m (grade de 0,005°, a mesma dos notebooks 01 e 05) × hora do dia (0–23) × tipo de dia
  (útil / fim de semana) × chovendo (sim / não) = 96 combinações por célula.
- **Células consideradas:** as que têm ≥ 1 atropelamento com coordenada válida em 2022–2025 (~3 mil; ~300 mil
  linhas). Limitação declarada: o conjunto de células usa os quatro anos (só a presença da célula, nunca a contagem
  do teste nas variáveis).
- **Alvo:** número de atropelamentos na célula × combinação, no período.
- **Exposição:** número de horas daquele tipo (hora × tipo de dia × chovendo) no período, calculado da série horária
  do Open-Meteo (`data/raw/open_meteo_precipitacao_sp_2022_2025.csv`; chovendo = ≥ 0,2 mm na hora). A exposição é a
  mesma para todas as células (chuva de ponto único para a cidade — limitação).
- **Junção sinistro → hora de chuva:** igual ao notebook 05 (valor do Open-Meteo marcado na hora seguinte, que cobre
  o intervalo do sinistro).
- **Divisão temporal:** treino 2022–2023, teste 2024, checagem 2025 (não fatais incompletos; só como checagem).
- **Excluídos:** registros sem hora ou sem coordenada válida (~4%), como no notebook 05.
- **Variáveis (só com o treino):** hora (seno/cosseno), fim de semana, chovendo; histórico de atropelamentos da
  célula no treino (log(1 + n)); célula tem grupo do DBSCAN refeito só com o treino (como no 05) e o peso desse grupo;
  rodovia (maioria dos atropelamentos de treino da célula em estrada/rodovia).
- **Fora de propósito (trabalho futuro):** escolas e semáforos do notebook 04.

## 3. Modelos e métricas

**Modelos**
1. **Linha de base:** taxa histórica da célula no treino × perfil horário médio da cidade (hora × tipo de dia).
2. **Regressão de Poisson** (statsmodels, `offset = log(exposição)`): explicativa; coeficientes → razões de taxa com
   IC 95% (ex.: "com chuva, o risco é multiplicado por X").
3. **Gradient boosting com perda de Poisson** (scikit-learn `HistGradientBoostingRegressor(loss="poisson")`, alvo =
   contagem/exposição, `sample_weight` = exposição); hiperparâmetros por validação cruzada agrupada por célula
   (`GroupKFold`, 5 dobras) dentro do treino.

**Regra de escolha (fixada antes do teste):** menor deviance de Poisson média na validação cruzada; empate prático
(< 1% de diferença) → regressão de Poisson.

**Métricas no teste 2024**

| Pergunta | Métrica |
|---|---|
| Prevê melhor que o histórico? | D² de Poisson contra a linha de base |
| Onde pôr os nós? | Taxa de acerto e PAI no top 1% e top 5% das células (contra o ranking só pelo histórico) |
| Quando acionar o nó? | ROC-AUC e PR-AUC de "≥ 1 atropelamento" por linha (célula × combinação) |
| Números confiáveis? | Calibração: total previsto × observado por decil de risco e no total |
| A chuva importa? | Razão de taxas com IC (Poisson) + taxa da cidade por hora chuvosa × hora seca |

**Critério de "bom" (declarado antes):** (1) D² > 0 contra a linha de base; (2) top 5% concentra mais atropelamentos
de 2024 que o ranking histórico; (3) erro no total de 2024 ≤ 10%. Se falhar: documentar como resultado e manter o
plano B (prioridade pelo índice do DBSCAN).

## 4. Função `risco()` e arquivos

Assinatura inalterada: `risco(lat, lon, quando, chuva_mm) -> dict`.

| Chave | Conteúdo |
|---|---|
| `probabilidade_atropelamento_1h` | P(≥ 1 atropelamento na célula na próxima hora) = 1 − e^(−λ) (**protagonista**) |
| `risco_relativo` | λ ÷ λ médio da cidade (média ponderada pela exposição) |
| `nivel` | baixo / medio / alto pelo risco de atropelamento; cortes = quantis 50% e 90% de λ no teste 2024 (**muda de sentido**: antes vinha da gravidade) |
| `probabilidade_fatal` | modelo de gravidade do notebook 05 (sem mudança) |
| `probabilidade_atropelamento_fatal_1h` | produto das duas probabilidades (base da estimativa de impacto, dia 18) |
| `cluster_id`, `rank_prioridade`, `rank_urbano` | grupo oficial do notebook 03 (sem mudança) |
| `motivos` | "horário de pico", "madrugada", "noite", "chuva" (só se a razão de taxas da chuva tiver IC acima de 1), "fim de semana", "rodovia", "ponto crítico top 20" / "ponto crítico (DBSCAN)", "local com histórico de mortes" |

Célula sem histórico (inclusive fora de São Paulo): usa as variáveis de célula vazia (histórico 0, sem grupo) — o
modelo devolve uma taxa baixa, sem erro.

**Arquivos**
- `src/estudo_b_risco_vida/06_modelo_risco_ocorrencia.ipynb` (novo, mesmo estilo dos anteriores).
- `models/modelo_risco.joblib` (novo); `models/modelo_gravidade.joblib` fica como está.
- `src/estudo_b_risco_vida/risco.py`: funções novas de agregação e exposição (usadas pelo notebook e pela função,
  para treino e produção montarem as variáveis do mesmo jeito) e carga em cache dos dois modelos.
- Evidências em `docs/evidencias/estudo_b/06_*` (gráficos, tabela de métricas, saída do pytest).

## 5. Testes (TDD: escritos antes, vistos falhando)

- Os 15 testes atuais continuam passando (o de "sábado 3h com chuva tem probabilidade **fatal** maior" segue valendo).
- Novos com valores calculados à mão em dados sintéticos:
  - exposição: série de exemplo com horas de chuva e secas conhecidas → contagem exata por hora × tipo de dia × chuva;
  - agregação: poucos atropelamentos sintéticos → contagem por célula × combinação igual à tabela feita à mão.
- Novos de comportamento:
  - Largo da Concórdia (-23,54231; -46,61655), terça 18h30, seco → `probabilidade_atropelamento_1h` em (0, 1) e
    `nivel` válido;
  - mesmo local, dia útil 18h → risco de atropelamento maior que dia útil 4h;
  - Largo → risco maior que uma célula sem histórico, mesma hora;
  - ponto fora de SP (-22,90; -43,20) → não quebra, `cluster_id` None.

## 6. Fora do escopo desta etapa

- Estimativa de impacto (atropelamentos e mortes evitados): dia 18, no PDF, usando a saída deste modelo + eficácias
  da bibliografia, marcada como resultado esperado (regra 8).
- Escolas, semáforos e alagamento como variáveis do modelo.
- Mudanças no modelo de gravidade.
