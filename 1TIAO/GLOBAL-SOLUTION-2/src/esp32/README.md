# Nó ESP32 da faixa (Wokwi)

Nó instalado na faixa de pedestres (no piloto, o Largo da Concórdia): semáforo de carros e de pedestre, botão de
**travessia estendida**, buzzer (sinal sonoro) e **matriz de LED** como placa inteligente. Recebe o modo por MQTT
(normal, pedestre, escola, chuva, ambulância) e decide sozinho o ciclo, as prioridades e o botão. Spec:
`docs/specs/2026-11-13-no-esp32-design.md`.

**Estado (13/11/2026):** funcionando no Wokwi, com aceitação ponta a ponta (MQTT real + banco) registrada em
`docs/evidencias/esp32/aceitacao.md`.

## Como rodar

1. Abra o projeto no Wokwi: **LINK_WOKWI** (ou crie um projeto ESP32 em wokwi.com e envie os 5 arquivos desta pasta:
   `sketch.ino`, `logica.h`, `logica.cpp`, `diagram.json`, `libraries.txt`).
2. **Entre na sua conta do Wokwi** antes de iniciar: sem login, o ESP32 simulado não tem internet (o gateway recusa
   usuário anônimo) e o MQTT não conecta. O nó funciona do mesmo jeito sem rede (botão e ciclo).
3. Inicie a simulação e, no computador, em `1TIAO/GLOBAL-SOLUTION-2`:

```bash
../../.venv/Scripts/python.exe src/central/gravador_mqtt.py        # grava os eventos do nó na tabela eventos
../../.venv/Scripts/python.exe src/central/roteiro_demo.py         # demonstração (~5 min)
../../.venv/Scripts/python.exe src/central/roteiro_demo.py --teste # roteiro de aceitação (~7 min)
```

**Plano B sem rede:** o mesmo JSON do MQTT pode ser digitado no monitor serial do Wokwi, uma linha por comando, por
exemplo `{"v":1,"id":"a1","ts":"2026-11-15T18:00:00-03:00","modo":"ambulancia","eta_s":20}`.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `logica.h`, `logica.cpp` | Cérebro do nó, sem hardware: modos, prioridade, ciclo e tempos, texto da matriz, buzzer, botão (inclusive o bloqueio por ambulância) |
| `sketch.ino` | Casca: Wi-Fi, MQTT, leitura do botão, LEDs, buzzer e matriz; valida o JSON do comando (igual a `src/central/mensagens.py`) |
| `diagram.json`, `libraries.txt` | Circuito e bibliotecas (PubSubClient, ArduinoJson, MD_Parola, MD_MAX72XX) |

**Ligações:** LEDs dos carros vermelho/amarelo/verde nos GPIO 25/26/27 e do pedestre vermelho/verde nos GPIO 32/33
(resistores de 220 Ω); botão no GPIO 14 (pull-up interno); buzzer no GPIO 13; matriz MAX7219 (4 módulos) com DIN 23,
CLK 18 e CS 5.

## Modos

Faixa de 10 m (configurável); verde do pedestre = 10 ÷ 1,2 ≈ 8 s (normal) ou 10 ÷ 0,8 ≈ 12,5 s (estendida).

| Modo | Matriz | O que muda |
|---|---|---|
| Normal | VIA SEGURA | Carros 20 s verde, 3 s amarelo, 2 s vermelho total; pedestre 8 s + 4 s piscando |
| Botão | TRAVESSIA ESTENDIDA | Encurta o verde dos carros (mínimo 8 s), pedestre 12,5 s, bipe lento (sinal sonoro) |
| Pedestre (visão) | PEDESTRE NA VIA - REDUZA | Com a faixa ainda ocupada, o vermelho dos carros estende-se até +10 s |
| Escola | ESCOLA - DEVAGAR 30 KM/H | Toda travessia é estendida, com sinal sonoro |
| Chuva | CHUVA - REDUZA / ALAGAMENTO A FRENTE | Amarelo 4 s, vermelho total 3 s |
| Ambulância | AMBULANCIA - ABRA CAMINHO | Com chegada em ≤ 30 s: verde dos carros até ela passar; o botão é **recusado** ("PRIORIDADE AMBULANCIA") e o pedido é **atendido depois**; quem já atravessa nunca é cortado |

Prioridade: ambulância > pedestre já na faixa > travessia estendida > chuva > escola > pedestre detectado > normal.
Sem comando por 120 s, volta ao normal; a ambulância sem "fim" termina sozinha em chegada + 15 s.

## Limitações

- Simulação no Wokwi, não hardware real; no plano gratuito a simulação roda abaixo do tempo real (20% a 50%), então
  os tempos do log são simulados.
- Broker público sem autenticação: só para demonstração (instalação real: TLS, usuário e senha, ACL por tópico).
  As mensagens não têm dado pessoal.
- O evento é publicado com QoS 0 (limite da biblioteca PubSubClient); o gravador não duplica, mas uma mensagem pode se
  perder se a rede cair.
- Comprimento da faixa (10 m) e velocidades de projeto (1,2 e 0,8 m/s) a confirmar; posição da ambulância simulada;
  um sentido de veículos.
