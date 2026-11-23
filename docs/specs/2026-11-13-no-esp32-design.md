# Nó ESP32 da faixa (Wokwi) — design

**Data:** 13/11/2026 · **Status:** aprovado em conversa, aguardando revisão da spec escrita
**Projeto:** Via Segura SP (GS FIAP 2026.2, entrega 19/11/2026) · **Pasta:** `src/esp32/` e `src/central/`

## 1. Objetivo e critério de sucesso

O nó instalado na faixa de pedestres (no piloto, o Largo da Concórdia) avisa motoristas e pedestres e controla o
semáforo conforme o contexto. Ele roda **no Wokwi, no navegador** (link público do projeto); a maquete física é extra.

**Sucesso:** no vídeo de 5 minutos, o nó no Wokwi troca de modo por comando vindo do Python (via MQTT), com LEDs,
matriz de LED e buzzer reagindo; o botão de travessia estendida funciona, inclusive bloqueado quando há ambulância
próxima; e os eventos do nó aparecem na tabela `eventos` do banco.

**Etapas (decisão de 13/11):** agora, o nó e um **roteiro** em Python que manda os modos em sequência; em 17/11, a
central passa a mandar os mesmos comandos a partir dos dados reais (visão, horário de escola, previsão do Open-Meteo,
posição simulada da ambulância), **sem mudar o ESP32**. Tudo o que for simulado é identificado como tal (regra 8).

## 2. Decisões

| Decisão | Escolha | Por quê |
|---|---|---|
| Onde roda | Wokwi no navegador | Grátis; a banca abre o link; MQTT funciona pelo Wi-Fi simulado |
| Placa inteligente | Matriz de LED MAX7219 (4 módulos, 32×8), texto correndo | Parece placa de rua de verdade |
| Quem dispara os modos | Roteiro agora, central depois (mesmo contrato) | Não trava o ESP32 esperando a central |
| Quem decide o botão | O próprio nó, na hora; avisa a central | Botão de segurança não pode depender da internet |
| Arquitetura | Nó com lógica própria; central só manda o modo | Coerente com o botão local; central simples |
| Testes do C++ | Aceitação no Wokwi (log da serial + lista de verificação) | Não há compilador C++ na máquina; instalar custaria meio dia |

## 3. Peças (Wokwi)

- ESP32 DevKit (Wi-Fi `Wokwi-GUEST`).
- Semáforo dos carros: LEDs vermelho, amarelo e verde. Semáforo do pedestre: LEDs vermelho e verde.
- Botão de travessia estendida (entrada com pull-up interno).
- Buzzer (piezo).
- Matriz de LED MAX7219, 4 módulos (biblioteca MD_Parola + MD_MAX72XX).
- Broker MQTT público de testes: `test.mosquitto.org` (reserva: `broker.hivemq.com`), porta 1883.

## 4. Organização do código

| Arquivo | Responsabilidade |
|---|---|
| `src/esp32/logica.h`, `logica.cpp` | "Cérebro" do nó **sem dependência de hardware nem de Arduino**: modo ativo pela prioridade, ciclo e tempos do semáforo, texto da matriz, padrão do buzzer, decisão do botão (inclusive bloqueio por ambulância), queda da central. Entrada: tempo atual (ms), comandos já decodificados, botão. Saída: estado das luzes, texto, buzzer e eventos a publicar |
| `src/esp32/sketch.ino` | Casca de hardware: lê o botão (com debounce), acende LEDs, toca o buzzer, escreve na matriz, conecta Wi-Fi/MQTT, decodifica o JSON do comando e publica estado e eventos. **Não decide nada** |
| `src/esp32/diagram.json`, `libraries.txt` | Montagem e bibliotecas do Wokwi |
| `src/esp32/README.md` | Como abrir no Wokwi, ligações, modos e limitações |
| `src/central/mensagens.py` | Contrato MQTT: tópicos, construção e validação dos comandos e dos eventos |
| `src/central/roteiro_demo.py` | Sequência de demonstração (normal → pedestre → escola → chuva → ambulância se aproximando → fim), publicada via MQTT |
| `src/central/gravador_mqtt.py` | Escuta `.../evento`, valida e grava em `eventos` (origem `esp32`) |

Dependência nova no Python: `paho-mqtt`.

## 5. Comportamento

**Comprimento da faixa C** configurável (padrão 10 m: o do Largo da Concórdia ainda não foi medido). Velocidades de
projeto: **1,2 m/s** (travessia normal, referência já usada no projeto) e **0,8 m/s** (estendida, conservadora para
cadeira de rodas, andador e idosos). As duas precisam de fonte citada no PDF.

**Prioridade (da maior para a menor):** ambulância > pedestre já na faixa > travessia estendida (botão) > chuva >
escola > pedestre detectado > normal.

| Modo | Matriz | Semáforo | Buzzer |
|---|---|---|---|
| Normal | "VIA SEGURA" | Carros: verde 20 s → amarelo 3 s → vermelho total 2 s. Pedestre: verde C/1,2 (≈ 8 s) → vermelho piscando 4 s → vermelho total 2 s | — |
| Botão (estendida) | "TRAVESSIA ESTENDIDA" | Antecipa o fim do verde dos carros (mínimo 8 s de verde já dado). Pedestre: verde C/0,8 (≈ 12,5 s) | Bipe lento no verde; rápido no pisca |
| Pedestre detectado (visão) | "PEDESTRE NA VIA · REDUZA" | Se `faixa_ocupada` = verdadeiro ao fim do verde do pedestre, vermelho dos carros estende-se até +10 s | — |
| Escola | "ESCOLA · DEVAGAR 30 KM/H" | Toda travessia é estendida | Sinal sonoro na travessia |
| Chuva | "CHUVA · REDUZA" ou, com `alagamento`, "ALAGAMENTO À FRENTE" | Amarelo 4 s; vermelho total 3 s | — |
| Ambulância | "AMBULÂNCIA · ABRA CAMINHO" | Com `eta_s` ≤ 30: verde dos carros (sentido dela) até `fim`. Se o verde do pedestre já começou, termina a travessia (inclusive estendida) antes | Alerta intermitente |

**Botão durante a ambulância (decisão de 13/11):** se o modo ambulância está ativo com `eta_s` ≤ **30 s** (raio de
bloqueio medido em tempo: distância ÷ velocidade, calculado por quem manda o comando), o botão **não estende a
travessia agora**: matriz "PRIORIDADE AMBULÂNCIA", bipe curto de recusa, pedestre continua no vermelho, evento
`botao_recusado_ambulancia`. O pedido **fica guardado** e é atendido (travessia estendida + sinal sonoro) assim que a
ambulância passa, com evento `pedido_atendido_apos_ambulancia`.

**Segurança:**
- Quem já está atravessando nunca é cortado (vale para a ambulância).
- O botão funciona sem conexão.
- Sem nenhum comando por **120 s**, o nó volta ao normal (evento `sem_central_volta_normal`).
- O modo ambulância termina sozinho em `eta_s` + **15 s** se o `fim` não chegar (o bloqueio do botão nunca fica preso).
- Ao ligar, o nó começa no normal, com carros no vermelho por 2 s.

## 6. Contrato MQTT

Prefixo: `viasegura/gs2026/no/largo-concordia/`. QoS 1 para comando e evento.

| Tópico | Direção | Conteúdo |
|---|---|---|
| `comando` | central → nó | `{"v":1,"id":"<uuid>","modo":"normal|pedestre|escola|chuva|ambulancia","ts":"<ISO -03:00>"}` + opcionais: `faixa_ocupada` (bool, pedestre), `alagamento` (bool, chuva), `eta_s` (número ≥ 0, ambulância), `fim` (bool, ambulância) |
| `estado` | nó → central (retido) | `{"v":1,"modo":"…","fase":"carros_verde|carros_amarelo|vermelho_total|pedestre_verde|pedestre_pisca","ultimo_comando":"<id>","boot":"<id do boot>"}` |
| `evento` | nó → central | `{"v":1,"tipo":"…","seq":<int>,"boot":"<id>","detalhe":{…}}` |

Tipos de evento: `botao_pressionado`, `travessia_estendida`, `botao_recusado_ambulancia`,
`pedido_atendido_apos_ambulancia`, `modo_alterado`, `sem_central_volta_normal`, `comando_invalido`.

Comando inválido (JSON quebrado, `v` ≠ 1, modo desconhecido, `eta_s` negativo): o nó ignora, mantém o modo e publica
`comando_invalido`. O Python valida antes de publicar.

**Gravação no banco:** cada evento vira uma linha de `eventos`: `origem='esp32'`, `tipo` do evento, `cluster_id` do
Largo da Concórdia, `payload_json` com o evento e `demonstracao: true`, `timestamp` = hora de chegada (-03:00),
`chave = "esp32:<no>:<boot>:<seq>"` (idempotente com `ON CONFLICT DO NOTHING`, como a visão).

**Privacidade e segurança:** as mensagens não têm dado pessoal. O broker público não tem autenticação; serve à
demonstração. Instalação real: TLS e usuário/senha no broker, tópicos com ACL (vai nas limitações do PDF).

## 7. Testes

- **Python (pytest, sem rede):** `mensagens.py` (comandos válidos e inválidos, campos por modo); `roteiro_demo.py`
  (ordem dos modos, `eta_s` decrescente até `fim`, todos os comandos válidos); `gravador_mqtt.py` com banco em
  memória e mensagens falsas (tradução para `eventos`, idempotência, mensagem quebrada não derruba o gravador).
- **Integração com broker real:** um teste marcado `slow`, opcional (publica e recebe um comando).
- **Firmware: aceitação no Wokwi.** Roteiro de teste + log da serial conferido contra esta lista:
  1. cada modo acionado mostra a mensagem e o ciclo da tabela;
  2. botão no normal → travessia estendida com sinal sonoro;
  3. botão com ambulância a ≤ 30 s → recusado, "PRIORIDADE AMBULÂNCIA", pedido atendido depois do `fim`;
  4. ambulância chegando com pedestre já atravessando → a travessia termina antes;
  5. comando inválido → ignorado + evento;
  6. 120 s sem comando → volta ao normal;
  7. ambulância sem `fim` → termina em `eta_s` + 15 s.
  Log e GIF da tela em `docs/evidencias/esp32/`. A execução no navegador é feita pela autora (ou por automação do
  navegador, se disponível), com a lista acima.

## 8. Fora do escopo

Maquete física; teste automático do C++ no PC (extra, se sobrar tempo); mais de um nó; a central completa
(17/11); semáforo com mais de um sentido de veículos.

## 9. Limitações (para o PDF)

Simulação (Wokwi), não hardware real; broker público sem autenticação; comprimento da faixa e velocidades de projeto
a confirmar; posição da ambulância simulada; um sentido de veículos.
