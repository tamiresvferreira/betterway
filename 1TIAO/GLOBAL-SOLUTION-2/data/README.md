# Dados

| Arquivo esperado em `raw/` | Fonte | Como obter | Observação |
|---|---|---|---|
| Sinistros (CSV) | Infosiga — Detran-SP | https://infosiga.detran.sp.gov.br → aba Dados Abertos | Filtrar capital, 2022–2025. Fatais desde 2015, não fatais desde 2019. |
| Semáforos e travessias semaforizadas (`raw/osm/`) — **fonte principal** | OpenStreetMap (ODbL) | Overpass API, município de São Paulo (`admin_level=8`), `highway=traffic_signals`, `crossing=traffic_signals`, `crossing:signals=yes`, com `out meta` | O notebook 04 baixa sozinho se faltar. Recente, mas mantido por voluntários. Citar "© colaboradores do OpenStreetMap". |
| Escolas e semáforos 2018 (`raw/geosampa/`) | GeoSampa — Prefeitura de SP | WFS público `wfs.geosampa.prefeitura.sp.gov.br`, camadas `equipamento_educacao_rede_publica`, `equipamento_educacao_infantil_rede_publica`, `equipamento_educacao_ceu` e `semaforo`, em GeoJSON (EPSG:4326) | O notebook 04 baixa sozinho se faltar; a data do download vai no nome do arquivo. Semáforos: cadastro da CET de 2018, usado só como comparação. Escolas: as camadas não informam data. Citar a fonte. |
| Pontos de alagamento | CGE — Prefeitura de SP | https://www.cgesp.org e relatórios anuais | Base montada pelo projeto; parcial (declarar). |
| Previsão de chuva | Open-Meteo | API, sem chave | Consultada em tempo real pela central. |

Os arquivos de `raw/` não vão para o Git por tamanho. Os dados tratados ficam em `processed/`.
