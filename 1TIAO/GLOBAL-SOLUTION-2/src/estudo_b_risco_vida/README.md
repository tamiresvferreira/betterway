# Estudo B: risco à vida (atropelamentos em São Paulo, 2022–2025)

Dados abertos do Infosiga SP (Detran-SP), dicionário v1.8, extração de 19/10/2026.

## Notebooks (rodar nesta ordem)

| # | Notebook | O que faz | Gera |
|---|---|---|---|
| 01 | `01_limpeza_analise_atropelamentos_sp.ipynb` | Lê o `dados_infosiga.zip`, faz o recorte (capital, 2022–2025, sem `NOTIFICACAO`), limpa os dados, confere com o painel do Infosiga e faz a análise exploratória | bases em `data/processed/` |
| 02 | `02_modelo_letalidade_atropelamentos_sp.ipynb` | Regressão logística: o que aumenta a chance de um pedestre atropelado morrer | razões de chances, probabilidades previstas |
| 03 | `03_dbscan_pontos_criticos.ipynb` | DBSCAN (haversine, fatal com peso 3) + índice de concentração da CET, ranking, mapa e banco SQLite | `data/processed/seguranca_viaria.db`, `docs/evidencias/estudo_b/` |

## Como rodar

1. Baixe o `dados_infosiga.zip` em <https://infosiga.detran.sp.gov.br> (aba *Dados Abertos e Documentos*) e
   coloque em `1TIAO/GLOBAL-SOLUTION-2/data/raw/` **sem extrair**. O arquivo (141 MB) não vai para o Git.
   As bases tratadas de `data/processed/` já estão versionadas: os notebooks 02 e 03 rodam sem o zip.
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

## Pendências

- **Comparação completa com o ranking da CET:** o PDF público da reunião de 11/03/2026 é só a transcrição, sem
  a tabela das 244 concentrações. A função de comparação está pronta no notebook 03 (seção 5) e roda sozinha
  quando existir `data/processed/cet_concentracoes.csv` (`nome;rank_cet;lat;lon`).
