# Estudo B: risco à vida (atropelamentos em São Paulo, 2022–2025)

Dados abertos do Infosiga SP (Detran-SP), dicionário v1.8, extração de 19/10/2026.

## Notebooks (rodar nesta ordem)

| # | Notebook | O que faz | Gera |
|---|---|---|---|
| 01 | `01_limpeza_analise_atropelamentos_sp.ipynb` | Lê o `dados_infosiga.zip`, faz o recorte (capital, 2022–2025, sem `NOTIFICACAO`), limpa os dados, confere com o painel do Infosiga e faz a análise exploratória | bases em `data/processed/` |
| 02 | `02_modelo_letalidade_atropelamentos_sp.ipynb` | Regressão logística: o que aumenta a chance de um pedestre atropelado morrer | razões de chances, probabilidades previstas |
| 03 | `03_dbscan_pontos_criticos.ipynb` | DBSCAN (haversine, fatal com peso 3) + índice de concentração da CET, ranking, mapa e banco SQLite | `data/processed/seguranca_viaria.db`, `docs/evidencias/estudo_b/` |
| 04 | `04_entorno_pontos_criticos.ipynb` | Escolas (300 m, GeoSampa) e semáforos/travessias (150 m, OSM como fonte principal e GeoSampa 2018 como comparação) em volta de cada grupo; grava as colunas na tabela `clusters`, gera a planilha de verificação manual e confirma o piloto | colunas novas em `clusters`, `mapa_entorno.html`, `verificacao_manual.csv` |

## Como rodar

1. Baixe o `dados_infosiga.zip` em <https://infosiga.detran.sp.gov.br> (aba *Dados Abertos e Documentos*) e
   coloque em `1TIAO/GLOBAL-SOLUTION-2/data/raw/` **sem extrair**. O arquivo (141 MB) não vai para o Git.
   As bases tratadas de `data/processed/` já estão versionadas: os notebooks 02 e 03 rodam sem o zip.
   As camadas do GeoSampa (escolas e semáforos 2018) e do OSM (semáforos) são baixadas pelo notebook 04 se
   não estiverem em `data/raw/geosampa/` e `data/raw/osm/`. Se o notebook 03 for rodado de novo, ele recria o banco: rode o 04 em seguida.
2. Na raiz do repositório:
   ```
   python -m venv .venv
   .venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
   pip install -r 1TIAO/GLOBAL-SOLUTION-2/requirements.txt
   ```
3. Rode os notebooks em ordem (no Jupyter ou com
   `jupyter nbconvert --to notebook --execute --inplace <arquivo>`). Os notebooks encontram a pasta do
   projeto sozinhos, subindo pelas pastas até achar `data/raw`.

## Principais achados

1. **Idosos:** pedestres com 60 anos ou mais são **21,6% das vítimas, mas 46,6% das mortes**. A letalidade é de
   14,2% para eles e de 4,5% para os mais novos. No modelo, a chance de morte na faixa 80+ é ~9,7 vezes a de um
   adulto de 30–39 anos.
2. **Madrugada:** ser atropelado de madrugada multiplica a chance de morte por **~4,3** em relação à tarde,
   comparando mesma idade, sexo, tipo de via e ano (AUC do modelo = 0,766).
3. **Pontos críticos (DBSCAN, eps 100 m, min_samples 8):** 290 concentrações. No ranking urbano (sem rodovias
   e sem pontos empilhados), o grupo do **Largo da Concórdia / Rangel Pestana** é o **26º de 273 (top 10%)** e
   tem o **4º maior volume ponderado da cidade**. O grupo vizinho, Parque Dom Pedro II / Rangel Pestana, é o
   14º e tem o maior volume. Já a Av. Celso Garcia, mais para dentro da Zona Leste, cai para 94º. Isso
   sustenta o piloto no nó do Largo da Concórdia.
4. **Entorno (OSM + GeoSampa):** as bases de semáforos se cobrem só em parte (68% do cadastro de 2018 tem par
   no OSM a até 30 m; 76% do OSM tem par no cadastro), por isso `tem_semaforo` usa as duas. O grupo do Largo
   da Concórdia tem semáforo **nas duas bases** (6 nós OSM + 2 travessias semaforizadas; 4 cruzamentos no
   cadastro) e **nenhuma escola pública a até 300 m** (EE Padre Anchieta a ~340 m). O piloto se confirma para o
   modo "pedestre", atuando sobre semáforos que já existem. O modo "escola" entra como cenário de
   demonstração. No top 50 urbano, 20 grupos têm escola por perto e 7 não têm semáforo em nenhuma base. O
   foco Demas Zitto / Canal de Cocaia (Grajaú) junta as duas coisas e é o candidato a uma segunda fase.

## Pendências

- **Comparação completa com o ranking da CET:** o PDF público da reunião de 11/03/2026 é só a transcrição, sem
  a tabela das 244 concentrações. A função de comparação está pronta no notebook 03 (seção 5) e roda sozinha
  quando existir `data/processed/cet_concentracoes.csv` (`nome;rank_cet;lat;lon`).
- **Verificação manual (Street View):** preencher `docs/evidencias/estudo_b/verificacao_manual.csv` (foco para
  pedestre, contagem regressiva, data da imagem) para o top 10 urbano e o Largo da Concórdia.
- **Escolas do INEP:** o Catálogo de Escolas só existe num portal interativo; o download automático falhou.
  As escolas vêm do GeoSampa, que não informa data.
- **Pontos de alagamento do CGE:** sem base aberta. Entram como trabalho futuro (pedido via LAI) ou como base
  simulada identificada como tal na tabela `pontos_alagamento` (notebook 04, seção 6).
