# Roteiro: ESP32 (Wokwi) na demonstração

O nó da faixa e a plataforma conversam por MQTT (broker público `test.mosquitto.org`). O Wokwi simula o ESP32 no
navegador; a plataforma escuta o que ele publica e manda os comandos de modo.

## Antes de gravar (5 min)

1. Deixe a plataforma rodando (`streamlit run src/operador/app.py`) e entre como **transito1**.
2. Em outra aba, abra **https://wokwi.com/projects/480902516851985409** já **logada na sua conta do Wokwi**
   (sem login o ESP32 simulado fica sem internet e não conecta ao MQTT).
3. Clique em **Start** no Wokwi e espere a matriz mostrar **VIA SEGURA**.
4. Na plataforma, abra a **Sala de controle**: em poucos segundos o **Modo** deixa de ser "Sem sinal" e o semáforo
   desenhado passa a acompanhar o do Wokwi. Se não mudar em 30 s, use o plano B abaixo.

## Durante a gravação (cerca de 1 min)

1. **Plataforma → nó:** na Sala de controle, clique em **Ambulância**. No Wokwi, a matriz mostra
   **AMBULANCIA - ABRA CAMINHO** e o verde dos carros se mantém.
2. **Nó → plataforma:** clique em **Normal** e, no Wokwi, aperte o **botão da faixa**. Em segundos aparece em
   **Sinais do nó**: "Botão de travessia apertado" e depois "Verde do pedestre estendido".
3. **Validação:** clique em **Confirmar** num dos sinais. Ele passa a mostrar "Confirmado por … · Trânsito · hora".
   Entre como **saude1** para mostrar que a Saúde também valida, e que a área fica registrada.

Dica de tela: deixe o Wokwi e a plataforma lado a lado (duas janelas) para a câmera pegar a ida e a volta.

## Plano B (sem rede ou com o Wokwi fora do ar)

Na Sala de controle, abra **Demonstração sem o ESP32: simular um sinal do nó**, escolha o sinal e clique em
**Simular sinal do nó**. O sinal entra no feed com o selo **simulado** e pode ser validado do mesmo jeito. Diga na
narração que é a simulação do evento do nó.

Outro plano B, só no Wokwi: digite o comando JSON no monitor serial, uma linha por comando, por exemplo
`{"v":1,"id":"a1","ts":"2026-11-19T18:00:00-03:00","modo":"ambulancia","eta_s":20}`.

## Limites para citar

Simulação no Wokwi, não hardware real; no plano gratuito o tempo do Wokwi corre mais devagar que o real (20% a 50%).
Broker público sem autenticação, só para a demonstração.
