# Central

Decide o modo do nó da faixa (normal, pedestre, escola, chuva, ambulância), manda por MQTT e grava cada troca em
`alertas`, com o risco do local pela `risco()` do modelo. Também guarda o contrato MQTT e as ferramentas do nó.
Specs: `docs/specs/2026-11-16-central-design.md` (central) e `docs/specs/2026-11-13-no-esp32-design.md` (contrato).

**Estado (17/11/2026):** funcionando; testes em `tests/test_decisao.py`, `test_fontes.py`, `test_central.py`.

## Como rodar (de `1TIAO/GLOBAL-SOLUTION-2`, com o nó aberto no Wokwi)

```bash
../../.venv/Scripts/python.exe src/central/gravador_mqtt.py          # em outro terminal: eventos do nó → banco
../../.venv/Scripts/python.exe src/central/central.py                # demonstração (~5,5 min, todos os modos)
../../.venv/Scripts/python.exe src/central/central.py --ao-vivo      # relógio e chuva reais
../../.venv/Scripts/python.exe src/central/central.py --ao-vivo --ambulancia 600 40   # + ambulância SIMULADA
```

## Arquivos

| Arquivo | O que faz |
|---|---|
| `decisao.py` | `decidir(entradas)`: prioridade ambulância > chuva > escola > pedestre > normal; limiares 2,5 mm/h (chuva), 10 mm/h (alagamento), 60 s (ambulância); janelas de escola em dias úteis |
| `fontes.py` | Chuva prevista (Open-Meteo, por hora), pessoas na faixa (eventos da visão no banco), tempo de chegada da ambulância simulada |
| `central.py` | Laço: decide a cada 1 s; publica na troca e reenvia a cada 30 s (10 s com ambulância); grava `alertas` na troca de modo |
| `mensagens.py` | Contrato MQTT (tópicos, comandos e eventos) — o mesmo validado no ESP32 |
| `gravador_mqtt.py` | Eventos do nó → tabela `eventos` (origem `esp32`) |
| `roteiro_demo.py` | Sequência fixa de modos (teste de aceitação do nó) |
| `schema.sql` | Esquema do banco |

## Demonstração

Uma "manhã" de quarta-feira acelerada: 06:30 normal → 07:00 escola → 07:40 pedestres (visão, vídeo da Cidade do
México) → 08:00 chuva → 08:20 alagamento → 08:40 ambulância (600 m a 40 km/h, chega em 54 s) → 09:00 normal.
A chuva usa a **previsão real** do Open-Meteo quando ela passa do limiar; se não, entra **SIMULADA**. A ambulância é
sempre SIMULADA e a escola é cenário (o piloto não tem escola a menos de 300 m). Tudo isso aparece no `motivo`.

## Limitações

Chuva de um ponto só; alagamento pela intensidade da chuva (os pontos do CGE não foram obtidos); escola e ambulância
simuladas; broker público sem autenticação; risco do modelo do notebook 06 (célula de ~500 m).
