# Central (decide o modo do nó) — design

**Data:** 16/11/2026 · **Status:** aprovado em conversa, aguardando revisão da spec escrita
**Projeto:** Via Segura SP (GS FIAP 2026.2, entrega 19/11/2026) · **Pasta:** `src/central/`

## 1. Objetivo e sucesso

A central liga os módulos: lê a chuva prevista, o horário de escola, o que a visão viu na faixa e a posição
(simulada) de uma ambulância, **decide o modo do nó** pela mesma prioridade do ESP32, manda o comando por MQTT
(contrato de `mensagens.py`) e grava cada decisão em `alertas`, com o risco do local pela `risco()`.

**Sucesso:** no vídeo, `central.py --demo` faz o nó do Wokwi passar por todos os modos em ~6 minutos, com o motivo
de cada troca no log e em `alertas`; `--ao-vivo` roda com relógio e chuva reais.

## 2. Decisões (16/11)

| Decisão | Escolha |
|---|---|
| Como roda na demonstração | **Cenário com relógio acelerado** (`--demo`, padrão), usando dados reais onde existem; **`--ao-vivo`** como opção |
| Simulado | Identificado no `motivo` do alerta (regra 8): chuva simulada quando não chove de verdade, ambulância sempre simulada, escola é cenário (o piloto não tem escola a ≤ 300 m) |
| Lógica | Função pura `decidir()`, testada; fontes e laço finos |

## 3. Peças

| Arquivo | Responsabilidade |
|---|---|
| `src/central/decisao.py` | `Entradas`, `Decisao`, `decidir(entradas) -> Decisao` (pura) |
| `src/central/fontes.py` | `chuva_prevista_mm_h(lat, lon, quando, obter=...)` (Open-Meteo, timeout 10 s, `None` se falhar); `em_horario_escola(quando)`; `pedestres_da_visao(con, ...)`; `eta_ambulancia(t_s, distancia_inicial_m, velocidade_kmh)` |
| `src/central/central.py` | Laço: entradas → `decidir` → publica comando (QoS 1) → grava `alertas`; `--demo` / `--ao-vivo` |

## 4. Regras de `decidir()`

Prioridade: **ambulância > chuva > escola > pedestre > normal** (a do nó; "pedestre já na faixa" e o botão são
decididos no próprio nó).

| Modo | Quando | Campos do comando |
|---|---|---|
| ambulância | `ambulancia_eta_s` ≤ **60** | `eta_s` (arredondado, ≥ 0) |
| ambulância (fim) | a ambulância acabou de passar (`ambulancia_passou`) | `fim: true` — enviado uma vez, depois o modo de baixo |
| chuva | chuva ≥ **2,5 mm/h** (moderada) | `alagamento: true` se ≥ **10 mm/h** (forte; substituto até os pontos do CGE) |
| escola | 06:45–07:30, 11:45–13:15, 17:45–18:30 (dias úteis) | — |
| pedestre | a visão viu pessoa na faixa no último minuto | `faixa_ocupada: true` |
| normal | nenhum dos anteriores | — |

`Decisao` traz `modo`, `campos` (dict pronto para `mensagens.comando`) e `motivo` (texto curto em português, com
"SIMULADA"/"SIMULADO" quando for o caso).

## 5. Laço (`central.py`)

- A cada passo (1 s): monta `Entradas`, chama `decidir`.
- **Publica** quando a decisão muda (modo ou campos) **e** reenvia o modo atual a cada **30 s** (sinal de vida: o nó
  volta ao normal após 120 s sem comando).
- **Grava em `alertas`** só quando o modo (ou o alagamento) muda: `timestamp` -03:00, `cluster_id` 139, `modo`,
  `motivo` (com o risco: nível e probabilidade de atropelamento em 1 h), `risco` (= `probabilidade_atropelamento_1h`
  da `risco()` para o Largo da Concórdia, na hora do cenário e com a chuva usada), `enviado` (1 se o publish confirmou).
- Ambulância: o `eta_s` é reenviado a cada 10 s enquanto ela se aproxima.
- Erros de fonte (API fora, banco sem eventos) não derrubam a central: entram como "sem dado" no motivo.

**`--demo` (padrão, ~6 min):** relógio de cenário que começa às 06:50 de um dia útil; trechos:

| Hora do cenário | Duração real | O que acontece |
|---|---|---|
| 06:50 | 30 s | normal |
| 07:00 | 60 s | escola |
| 07:40 | 60 s | pedestres (eventos `pedestre_na_faixa` da visão, vídeo da Cidade do México) |
| 08:00 | 45 s | chuva (previsão real do Open-Meteo no log; se < 2,5 mm/h, chuva SIMULADA de 6 mm/h) |
| 08:20 | 45 s | alagamento (chuva SIMULADA de 12 mm/h) |
| 08:40 | ~75 s | ambulância SIMULADA: 750 m a 40 km/h (eta cai de ~67 s a 0), depois "fim" |
| 09:00 | 30 s | normal |

**`--ao-vivo`:** relógio real, chuva real (consulta a cada 10 min), eventos da visão do último minuto,
ambulância só com `--ambulancia DIST_M VEL_KMH`.

## 6. Testes

- `decidir`: cada linha da tabela §4, as prioridades (ambulância vence chuva etc.), limites exatos (2,5 e 10 mm/h,
  60 s), fora das janelas de escola e no fim de semana.
- `fontes`: Open-Meteo com resposta falsa (valor da hora certa), falha → `None`; `eta_ambulancia` decrescente e
  nunca negativo; janelas de escola.
- Laço: com cliente MQTT falso e banco em memória — publica na mudança, reenvia a cada 30 s, grava `alertas` só na
  troca de modo, `enviado` = 1, `motivo` contém "SIMULADA" na chuva simulada.
- Ponta a ponta (manual): `--demo` com o nó aberto no Wokwi; evidência em `docs/evidencias/central/`.

## 7. Limitações

Chuva para um ponto (não por quadra); alagamento por intensidade de chuva, não pelos pontos do CGE; escola e
ambulância simuladas; broker público sem autenticação; risco é o do modelo do notebook 06 (célula de ~500 m).
