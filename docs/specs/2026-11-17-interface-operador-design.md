# Interface do operador BetterWay (perfis, câmera simulada e sala de controle) — design

**Data:** 17/11/2026 · **Status:** aprovada em 17/11 (autenticação de verdade; roteiro do vídeo por último)
**Projeto:** BetterWay (antes "Via Segura SP"; GS FIAP 2026.2, entrega 19/11/2026 às 18h) · **Pasta:** `src/operador/`

## 1. Objetivo e sucesso

Mostrar o sistema como ele seria usado: a câmera da faixa (clipes sintéticos já processados pela visão), a fila de
ocorrências que o **Trânsito** valida, o despacho que a **Saúde** recebe e a visão de **Gestão** (o painel atual,
mais as animações do SUMO). A sala de controle mostra o estado do nó ESP32 ao vivo e permite mandar cenários.

**Sucesso:** os três perfis entram com usuário e senha de verdade e cada um só faz o que o seu perfil permite; a
ocorrência anda pelas etapas (§5) e o despacho move o nó no Wokwi. O roteiro do vídeo fica por último (§10).

## 2. Decisões (17/11)

| Decisão | Escolha |
|---|---|
| Perfis | **Trânsito** valida, **Saúde** recebe e despacha, **Gestão** só lê |
| Entrada | **Autenticação de verdade** (§4a): usuários no banco com senha em hash, sessão com prazo, bloqueio por tentativas e permissão conferida no servidor em cada ação. Nomes genéricos ("Operador(a) Trânsito 1"); senhas fora do Git. |
| Aviso fixo | "Ambiente de demonstração · sem integração com CET ou SAMU", em todas as telas |
| Câmera | Clipes do **Veo 3** (gerados pela Tamires) processados **antes** pela visão: anotados e borrados. O player toca o clipe que corresponde ao modo atual do nó; o botão "próximo clipe" é o plano B. |
| Suspeita de acidente | **Regra nova** na visão (protótipo, avaliada só nos clipes sintéticos) **e** botão "reportar ocorrência" para o operador |
| Sala de controle | Convive com os perfis: estado do nó ao vivo (MQTT), risco agora e botões de cenário |
| Tecnologia | Streamlit (o mesmo do painel), com player em HTML embutido para as sobreposições do operador |
| Visual | Marca BetterWay: fundo grafite, verde #00C27A, âmbar #FFB000, alerta #E63946, Montserrat |
| Regra 8 | Tudo que é sintético ou simulado é rotulado: "clipe sintético (Veo 3)", "ambulância SIMULADA". As métricas dos clipes ficam separadas dos resultados reais. |

## 3. Peças

| Arquivo | Responsabilidade |
|---|---|
| `src/visao/visao.py` (+) | `suspeitas_de_queda(deteccoes, faixa, fps, min_s=3.0) -> list[Suspeita]` (pura) |
| `src/visao/processar_clipes.py` | Para cada clipe em `data/raw/video/veo3/`: visão + borrão → `data/processed/veo3/<clipe>_anotado.mp4` (H.264, toca no navegador; fora do Git), eventos com `video_id = veo3_<clipe>` e `docs/evidencias/operador/avaliacao_clipes.csv` (esperado × obtido) |
| `src/visao/faixa_veo3.json` | A faixa da imagem-base (uma só, porque todos os clipes saem da mesma imagem); `<clipe>.faixa.json` sobrepõe essa faixa quando um clipe sair diferente |
| `src/operador/perfis.py` | Perfis e permissões (pura): `pode(perfil, acao) -> bool` |
| `src/operador/autenticacao.py` | Tabela `usuarios`, hash e conferência de senha, bloqueio, sessão; CLI `python src/operador/autenticacao.py criar <usuario> <perfil> "<nome>"` (pede a senha sem eco) |
| `src/operador/ocorrencias.py` | Tabela `ocorrencias` e as transições de estado (§5); a lógica é pura e a gravação é fina |
| `src/operador/camera.py` | Clipe por modo (playlist), HTML do player com as sobreposições |
| `src/operador/no_ao_vivo.py` | Assinante MQTT (um por servidor, via `st.cache_resource`): último `estado` retido e últimos eventos do nó |
| `src/operador/app.py` | Login, barra lateral, telas dos três perfis e a sala de controle |
| `src/dashboard/app.py` (~) | O corpo vira `render_painel()`, para a tela de Gestão reaproveitar; o `streamlit run` do painel continua igual |

## 4a. Autenticação

- `usuarios`: usuario (único), nome exibido, perfil, hash, sal, tentativas falhas, bloqueado_ate, ativo.
- Senha com **scrypt** (stdlib `hashlib.scrypt`, sal aleatório de 16 bytes por usuário), comparação em tempo
  constante (`hmac.compare_digest`); mínimo de 8 caracteres. A senha nunca é gravada nem registrada em log.
- **5 tentativas erradas → bloqueio de 5 min**; a mensagem de erro é a mesma para usuário inexistente e senha errada.
- Sessão expira após **30 min sem uso**; botão sair limpa a sessão.
- **Toda ação confere o perfil no servidor** (`pode()` antes de gravar ou publicar), não só esconde botões.
- Cada mudança de ocorrência grava quem fez (usuário), e cada entrada/saída/falha vai para `acessos` (sem senha).
- Usuários iniciais criados pelo CLI; o README diz como. As senhas do vídeo/avaliação ficam com a Tamires.

## 4. Regra de suspeita de acidente (protótipo)

Uma pessoa rastreada (ByteTrack) gera `suspeita_acidente` quando, por **≥ 3 s seguidos**:
- a caixa dela está **deitada** (largura ≥ 1,2 × altura);
- o ponto dela está **na faixa ou na pista** (polígono da faixa ampliado para a pista);
- ela quase não se move (< 0,3 m/s).

Pessoa sentada no meio-fio (fora da pista) e pessoa de pé parada não disparam.

Limites ditos no PDF:
- avaliada só em clipes sintéticos;
- não distingue queda de alguém que se deitou;
- não detecta o impacto;
- por isso a ocorrência nasce **pendente**, e um humano confirma ou descarta.

## 5. Ocorrências

Tabela nova `ocorrencias`: id, cluster_id, origem (`visao` | `operador`), tipo, `video_id`, segundo do clipe,
estado, cada horário de mudança, o perfil e o nome genérico de quem mudou. **Nenhuma imagem é guardada**, só o
identificador do clipe.

```
pendente ──Trânsito confirma──▶ confirmada ──Saúde despacha──▶ despachada ──Saúde encerra──▶ encerrada
    └────Trânsito descarta───▶ descartada (com motivo)
```

- Transição fora dessa ordem ou feita pelo perfil errado é recusada (função pura, testada).
- **Despachar** publica, pelo contrato de `mensagens.py`, a sequência da ambulância SIMULADA no nó: `eta_s` a cada
  10 s a partir de 600 m a 40 km/h, depois `fim`. Assim o Wokwi reage como na central.
- Com a `central.py` rodando ao mesmo tempo, os comandos se misturam. Por isso a sala de controle avisa: use um ou outro.

## 6. Telas

- **Trânsito:**
  - câmera (player com o modo do nó, o rótulo "clipe sintético (Veo 3)" e uma linha do tempo que acende os
    eventos da visão quando o vídeo passa por eles);
  - fila de pendentes, com confirmar e descartar;
  - botão "reportar ocorrência".
- **Saúde:** confirmadas e despachadas, com o local (Largo da Concórdia, risco agora), despachar e encerrar.
- **Gestão:** o painel atual (mapa de risco, indicadores, eventos), as ocorrências com o tempo de cada etapa, as
  animações do Estudo A e a avaliação dos clipes sintéticos (separada).
- **Sala de controle** (todos os perfis veem; só o Trânsito manda cenário): estado do nó ao vivo, risco agora e
  botões normal, pedestre, escola, chuva, alagamento e ambulância.

## 7. Escopo e ordem (pronto até 19/11 às 18h)

| Bloco | Conteúdo |
|---|---|
| **Mínimo** (~10–12 h) | Autenticação · perfis · ocorrências com transições · as três telas · despacho → MQTT · regra de queda + `processar_clipes` + CSV de avaliação · sala de controle básica |
| **Bom** (+5–6 h) | Linha do tempo dos eventos no player · clipe que segue o modo do nó · acabamento visual da marca · avaliação por categoria na Gestão |

Enquanto os clipes do Veo 3 não chegam, a câmera usa os vídeos já anotados do Pexels (CDMX e cadeirante).

## 8. Testes

- **Puras, rápidas:**
  - `suspeitas_de_queda`: deitada na faixa dispara; sentada no meio-fio, de pé parada e deitada por < 3 s não disparam;
  - transições e permissões de ocorrência;
  - `clipe_para_modo`;
  - sequência do despacho (`eta_s` decrescente, termina em `fim`, valida em `validar_comando`).
- **Autenticação:**
  - senha certa entra, errada não; a mensagem é a mesma para usuário inexistente;
  - 5 erros bloqueiam e o bloqueio expira; a sessão expira após 30 min sem uso;
  - a mesma senha em dois usuários dá hashes diferentes;
  - perfil sem permissão é recusado na função, não só na tela.
- **Interface (AppTest):**
  - sem login, só aparece a tela de entrada;
  - login por perfil;
  - Trânsito confirma → Saúde vê;
  - Gestão não tem botões de ação;
  - aviso de demonstração em todas as telas.
- **Lento:** `processar_clipes` em um clipe curto gera vídeo e eventos.

## 9. Fora do escopo

- Integração real com CET ou SAMU.
- Cadastro e recuperação de senha pela interface (usuários só pelo CLI).
- Reconhecimento facial e monitoramento de crime (decisão mantida).
- Guardar imagens de ocorrência.
- Treinar a regra de queda.

## 10. Roteiro do vídeo (por último)

Trânsito entra, vê a câmera, surge "suspeita de acidente", confirma → Saúde entra, vê a confirmada, despacha
(ambulância SIMULADA) → o nó no Wokwi entra em modo ambulância e volta → Gestão vê a ocorrência com os tempos, o mapa
de risco e as animações. Escrito e ensaiado depois de tudo pronto.
