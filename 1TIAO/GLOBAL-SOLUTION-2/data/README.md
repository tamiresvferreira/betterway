# Dados

| Arquivo esperado em `raw/` | Fonte | Como obter | Observação |
|---|---|---|---|
| Sinistros (CSV) | Infosiga — Detran-SP | https://infosiga.detran.sp.gov.br → aba Dados Abertos | Filtrar capital, 2022–2025. Fatais desde 2015, não fatais desde 2019. |
| Escolas, semáforos | GeoSampa — Prefeitura de SP | https://geosampa.prefeitura.sp.gov.br → Download de Arquivos | Shapefile; citar a fonte. |
| Pontos de alagamento | CGE — Prefeitura de SP | https://www.cgesp.org e relatórios anuais | Base montada pelo projeto; parcial (declarar). |
| Previsão de chuva | Open-Meteo | API, sem chave | Consultada em tempo real pela central. |

Os arquivos de `raw/` não vão para o Git por tamanho. Os dados tratados ficam em `processed/`.
