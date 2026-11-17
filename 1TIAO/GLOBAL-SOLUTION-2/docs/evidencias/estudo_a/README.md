# Estudo A — resultados esperados (simulação no SUMO)

Arquivos: `estudo_a_rodadas.csv` (30 rodadas), `estudo_a_resumo.csv` (média, mínimo e máximo das 5 sementes) e
`estudo_a_comparacoes.png`. Código em `src/simulacao/`.

## Resultados (média de 5 sementes; entre parênteses, mínimo–máximo)

| Comparação | Indicador | Sem o sistema | Com o sistema |
|---|---|---|---|
| Extensão para pedestre com mobilidade reduzida | pessoas surpreendidas no meio da faixa | **100%** | **0%** |
| | atraso médio por carro | 23,7 s | 25,3 s (+1,6 s) |
| | CO₂ por carro | 134,3 g | 137,3 g (+2,2%) |
| Semáforo atuado (adaptativo) | atraso médio por carro | 23,7 s | **10,3 s (−57%)** |
| | CO₂ por carro | 134,3 g | 113,8 g (−15%) |
| | espera média do pedestre | 57,1 s | 13,8 s |
| | pessoas com mobilidade reduzida surpreendidas | 100% | 100% |
| Prioridade para ambulância | tempo médio no trecho | 57,7 s | **37,5 s (−35%)** |
| | pior caso | 97,2 s | 42,8 s |

## Leitura

- **A extensão funciona e custa pouco:** com o verde fixo de 19 s numa faixa de 16 m, **toda** pessoa a 0,8 m/s
  é surpreendida no meio da faixa (precisa de 20 s); com a extensão, nenhuma. O custo para os carros é de 1,6 s de
  atraso e 2% de CO₂ por veículo.
- **O semáforo adaptativo sozinho melhora a fluidez, mas não a segurança:** reduz o atraso pela metade e o CO₂ em 15%,
  porém os verdes curtos deixam mais pessoas no meio da faixa (inclusive todas as de mobilidade reduzida). Por isso, no
  projeto, o adaptativo vem **junto** com a extensão do pedestre, nunca sozinho.
- **Ambulância:** abrir o verde quando ela está a 150 m reduz o tempo médio em 35% e o pior caso pela metade, sem
  cortar quem já está atravessando (a mesma regra do nó ESP32).

## Limitações

- Cruzamento **sintético** calibrado pelo do piloto, fluxos **estimados**; os números são esperados, não medidos.
- No SUMO o pedestre pode começar a atravessar até o último segundo do verde (não há "vermelho piscando" que impeça
  novas entradas, como no nó ESP32); isso infla as pessoas comuns surpreendidas, principalmente no semáforo atuado.
- Pessoas comuns surpreendidas na faixa nas rodadas da ambulância: 4,6 por rodada sem a prioridade e 5,0 com ela
  (a diferença vem de quem entra na faixa no mesmo passo de simulação da troca para o verde da ambulância).
- Sem aprendizado por reforço (extra do plano, fora por tempo) e sem alagamento.

## Mapa real: tentado e descartado

O recorte do OpenStreetMap em volta do piloto (`data/raw/osm/largo_concordia.osm`, fora do Git) foi convertido com o
netconvert e o semáforo-alvo foi encontrado a 66 m do centro do grupo de atropelamentos (cluster 139): faixa de 16 m
com 19 s de verde — os números usados na calibração. Ele foi descartado porque: (1) há uma faixa **sem semáforo a 3 m**
da faixa-alvo (duplicação do mapa), que atraía todos os pedestres; (2) as vias junto ao semáforo têm de 0,2 a 3 m
(pedaços de junção), onde os veículos não cabem para partir; (3) ao estender os fluxos, eles atravessavam outros
semáforos estimados e a rede engarrafava (246 s de atraso por carro). Corrigir isso passaria do limite de 1 hora
combinado.
