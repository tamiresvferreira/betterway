# Estudo A — resultados esperados (simulação no SUMO)

Arquivos: `estudo_a_rodadas.csv` (30 rodadas), `estudo_a_resumo.csv` (média, mínimo e máximo das 5 sementes) e
`estudo_a_comparacoes.png`. Código em `src/simulacao/`.

## Resultados (média de 5 sementes; entre parênteses, mínimo–máximo das rodadas)

Ciclo do tempo fixo: 75 s (avenida 40 s, transições 5 + 3 s, pedestre 19 s, transições 5 + 3 s).

| Comparação | Indicador | Sem o sistema | Com o sistema |
|---|---|---|---|
| Extensão para pedestre com mobilidade reduzida | pessoas surpreendidas no meio da faixa | **100%** | **0%** |
| | atraso médio por carro | 13,7 s (13,5–13,9) | 14,7 s (13,9–15,3), +1,0 s |
| | CO₂ por carro | 118,1 g | 120,0 g (+1,6%) |
| Semáforo atuado (adaptativo) | atraso médio por carro | 13,7 s (13,5–13,9) | **10,3 s (9,9–10,8), −25%** |
| | CO₂ por carro | 118,1 g | 113,8 g (−3,6%) |
| | espera média do pedestre | 19,3 s | 13,8 s |
| | pessoas comuns surpreendidas na faixa (por rodada) | 13,8 | 67,2 |
| | pessoas com mobilidade reduzida surpreendidas | 100% | 100% |
| Prioridade para ambulância | tempo médio no trecho | 46,9 s | **40,7 s (−13%)** |
| | pior caso entre todas as rodadas | 67 s | 57 s |
| | pessoas comuns surpreendidas na faixa (por rodada) | 13,8 | 11,8 |

## Leitura

- **A extensão funciona e custa pouco:** com o verde fixo de 19 s numa faixa de 16 m, **toda** pessoa a 0,8 m/s
  que começa a atravessar no verde é surpreendida no meio da faixa (precisa de 20 s); com a extensão, nenhuma. O
  custo é de 1,0 s de atraso e 1,6% de CO₂ por veículo.
- **O semáforo adaptativo sozinho melhora a fluidez, mas piora a segurança na faixa:** reduz o atraso em 25% e a
  espera do pedestre, porém os verdes curtos deixam cinco vezes mais pessoas no meio da faixa (67 por rodada contra
  14) e todas as de mobilidade reduzida. Por isso, no projeto, o adaptativo vem **junto** com a extensão.
- **Ambulância:** abrir o verde quando ela está a 150 m reduz o tempo médio em 13% e o pior caso de 67 para 57 s,
  sem aumentar as pessoas surpreendidas na faixa (11,8 contra 13,8 por rodada): a prioridade só é dada com a faixa
  vazia, a mesma regra do nó ESP32.

## Limitações

- Cruzamento **sintético** calibrado pelo do piloto, fluxos **estimados**; os números são esperados, não medidos.
- As sementes variam os pedestres e a velocidade dos motoristas; os fluxos de carros (`vehsPerHour`) chegam em
  intervalos fixos, por isso a faixa de variação do atraso é estreita.
- No SUMO o pedestre pode começar a atravessar até o último segundo do verde (não há "vermelho piscando" que impeça
  novas entradas, como no nó ESP32); isso infla as pessoas comuns surpreendidas, sobretudo no semáforo atuado.
- O semáforo atuado usa o programa do netconvert (verdes de até 50 s, transições de 5 s), não só o mesmo plano com
  detectores; a comparação mede "atuado × tempo fixo calibrado", não apenas o efeito dos detectores.
- A troca para o verde da ambulância é imediata, sem amarelo para a rua transversal.
- Sem aprendizado por reforço (extra do plano, fora por tempo) e sem alagamento.
- Correções feitas na revisão (17/11): a demanda passou a ser escrita em ordem de partida (antes o SUMO descartava,
  sem aviso, 32 de 87 pessoas nas rodadas da ambulância) e o ciclo do tempo fixo voltou a 75 s (uma regra alongava
  as transições de 5 s e o ciclo ia a 145 s). Os números acima já são os corrigidos.

## Mapa real: tentado e descartado

O recorte do OpenStreetMap em volta do piloto (`data/raw/osm/largo_concordia.osm`, fora do Git) foi convertido com o
netconvert e o semáforo-alvo foi encontrado a 66 m do centro do grupo de atropelamentos (cluster 139): faixa de 16 m
com 19 s de verde — os números usados na calibração. Ele foi descartado porque: (1) há uma faixa **sem semáforo a 3 m**
da faixa-alvo (duplicação do mapa), que atraía todos os pedestres; (2) as vias junto ao semáforo têm de 0,2 a 3 m
(pedaços de junção), onde os veículos não cabem para partir; (3) ao estender os fluxos, eles atravessavam outros
semáforos estimados e a rede engarrafava (246 s de atraso por carro). Corrigir isso passaria do limite de 1 hora
combinado.
