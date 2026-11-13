# Aceitação do nó ESP32 no Wokwi (13/11/2026)

**Como foi feito:** o projeto foi montado no Wokwi (navegador, conta anônima, por automação de navegador) com os 5
arquivos de `src/esp32/`. O `gravador_mqtt.py` e o `roteiro_demo.py --teste` rodaram no computador, falando com o nó
pelo broker público `test.mosquitto.org`. O botão foi apertado no simulador (pressão "segurada", porque o clique
automático, mais curto que 50 ms no tempo simulado, é descartado pelo filtro de repique, como deve). Alguns comandos
foram digitados no monitor serial (mesmo JSON do MQTT). Log completo: `serial_teste.txt` (boot `d476b0`); imagem:
`no_esp32_ambulancia_botao_recusado.png`.

**Tempo simulado:** no plano gratuito a simulação rodou entre 9% e 50% do tempo real; os milissegundos entre
colchetes no log são do relógio do ESP32 simulado, que é o que a lógica usa.

| # | Item (spec §7 e plano) | Evidência (log da serial / banco) | Resultado |
|---|---|---|---|
| 1 | Cada modo mostra a mensagem e o ciclo | `[2047] FASE carros_verde` → `[22047] carros_amarelo` → `[25047] vermelho_total` → `[27047] pedestre_verde` → `[35397] pedestre_pisca` (20 s, 3 s, 2 s, 8,35 s = 10 m ÷ 1,2 m/s, 4 s). Matriz: `VIA SEGURA`, `PEDESTRE NA VIA - REDUZA`, `ESCOLA - DEVAGAR 30 KM/H`, `CHUVA - REDUZA`, `ALAGAMENTO A FRENTE`, `AMBULANCIA - ABRA CAMINHO` | ok |
| 2 | Botão no normal → travessia estendida com sinal sonoro | `[25652] BOTAO` → `MATRIZ "TRAVESSIA ESTENDIDA"`; depois da ambulância, `travessia_estendida valor=12` (12,5 s = 10 m ÷ 0,8 m/s) | ok |
| 3 | Botão com ambulância a ≤ 30 s → recusado e atendido depois | `[110186] BOTAO` → `MATRIZ "PRIORIDADE AMBULANCIA"`, `botao_recusado_ambulancia valor=28`; com o fim da ambulância, `[116654] pedido_atendido_apos_ambulancia` e `[121669] travessia_estendida valor=12`. Repetido no fim: `[185156] botao_recusado_ambulancia valor=17` (imagem) | ok |
| 4 | Ambulância chega com pedestre atravessando → a travessia termina antes | `[126322] modo ambulancia` durante `pedestre_verde`; `[134206] pedestre_pisca` → `[138206] vermelho_total` → `[140206] carros_verde` | ok |
| 5 | Comando inválido → ignorado + evento | `COMANDO INVALIDO: {"v":1,"modo":"voo"}` → `EVENTO comando_invalido` (também no banco) | ok |
| 6 | 120 s sem comando → volta ao normal | **Não observado no Wokwi:** a simulação gratuita ficou lenta demais (≈ 7 s simulados em 2 min). Verificado por leitura do código: mesmo mecanismo de tempo do item 7 (`passo()`: `agora - ultimoComando_ > SEM_CENTRAL`) | não observado |
| 7 | Ambulância sem "fim" → termina em eta + 15 s | Entrou em `[126322]` com `eta_s` 20; `[161354] modo_alterado valor=0` (35,0 s depois) | ok |
| 8 | "fim" sem ambulância ativa não trava nada | Primeiro comando do roteiro de teste; o nó seguiu no ciclo normal, sem evento extra | ok |
| 9 | 5 pressões rápidas → um só `botao_pressionado` | `[123720]`…`[124353]`: 5 linhas `BOTAO`, 1 `EVENTO botao_pressionado` | ok |

**Banco (`eventos`, origem `esp32`), depois do roteiro:** `modo_alterado` 8, `botao_pressionado` 3,
`travessia_estendida` 1, `pedido_atendido_apos_ambulancia` 1, `comando_invalido` 1, `botao_recusado_ambulancia` 1;
todos com `cluster_id` 139 (Largo da Concórdia), horário -03:00 e chave `esp32:largo-concordia:d476b0:<seq>`.
Eventos de antes de o gravador ligar não estão no banco (não houve mensagem retida de evento, por desenho).

**Problemas encontrados e corrigidos durante a aceitação:**
- O Wokwi anônimo às vezes não tem internet (gateway respondeu 503 para usuário anônimo) → comandos também pela
  serial (plano B) e instrução de entrar na conta do Wokwi no README.
- Erro de compilação por caracteres de controle literais na leitura da serial → corrigido (`'\r'`, `'\n'`).
- MQTT reconectando a cada ~15 s simulados (keepalive padrão de 15 s com a simulação abaixo do tempo real) →
  keepalive de 60 s. Verificação: ver abaixo.
  **Verificação do keepalive (boot `bf20db`, sketch com `setKeepAlive(60)`):** uma única conexão em `[5000]` e
  nenhuma reconexão até `[41442]` (≈ 4,5 min reais). Antes: 7 reconexões entre `[130501]` e `[184150]`.
