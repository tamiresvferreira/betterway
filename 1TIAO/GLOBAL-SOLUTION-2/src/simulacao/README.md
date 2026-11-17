# Simulação (Estudo A) — SUMO

Cruzamento semaforizado **sintético calibrado pelo do piloto** (Largo da Concórdia): avenida com 3 faixas por sentido
× rua com 1 faixa, braços de 300 m, faixa de pedestre de 16 m e verde do pedestre de 19 s (os números do cruzamento
real Av. Rangel Pestana × Largo da Concórdia × R. Joaquim Nabuco, medidos no mapa do OpenStreetMap). Fluxos de
veículos e de pedestres **estimados** (não há contagem da CET). Os números são **resultados esperados** de simulação
(regra 8). Resultados e leitura em `docs/evidencias/estudo_a/`.

**Estado (17/11/2026):** feito; 4 testes com o simulador real (`tests/test_estudo_a.py`, marcados `slow`).

## Como rodar (de `1TIAO/GLOBAL-SOLUTION-2`)

```bash
../../.venv/Scripts/python.exe -m pip install eclipse-sumo            # SUMO 1.28 (traci/sumolib vêm em sumo/tools)
../../.venv/Scripts/python.exe src/simulacao/estudo_a.py              # 30 rodadas (~2 min) → estudo_a_rodadas.csv
../../.venv/Scripts/python.exe src/simulacao/resumo_estudo_a.py       # resumo + gráfico
../../.venv/Scripts/python.exe -m pytest tests/test_estudo_a.py -m slow
```

## Comparações (cada uma sem × com o sistema, 5 sementes, 30 min simulados)

| Comparação | Sem o sistema | Com o sistema |
|---|---|---|
| Pedestre | verde do pedestre fixo (19 s) | verde **estendido** enquanto houver pessoa com mobilidade reduzida (0,8 m/s) sem tempo de terminar — a regra do nó ESP32 |
| Semáforo | tempo fixo (40 s avenida / 19 s pedestre) | atuado (adaptativo, por detectores) |
| Ambulância | segue o ciclo | verde para ela a 150 m do cruzamento, **sem cortar quem está na faixa** (6 ambulâncias por rodada, em momentos diferentes do ciclo) |

Alagamento: fora, por tempo (combinado); já coberto pela central e pelo nó.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `estudo_a.py` | Gera a rede (netconvert), a demanda e roda as comparações pelo TraCI |
| `resumo_estudo_a.py` | Média (mín–máx) por comparação e o gráfico |
| `rede/cruzamento_*.net.xml` | Redes geradas (tempo fixo e atuado) |
