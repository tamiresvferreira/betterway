# Interface do operador BetterWay

Como o sistema seria usado na operação: a câmera da faixa, a fila de ocorrências que o **Trânsito** valida, o despacho
que a **Saúde** recebe e a visão de **Gestão**. A sala de controle mostra o nó ESP32 ao vivo (MQTT).
Spec: [docs/specs/2026-11-17-interface-operador-design.md](../../docs/specs/2026-11-17-interface-operador-design.md).

> **Ambiente de demonstração · sem integração com CET ou SAMU.** A ambulância despachada é SIMULADA; os clipes do
> Veo 3 são SINTÉTICOS e a avaliação deles fica separada dos resultados com dados reais.

## Rodar

Todos os comandos são rodados de `1TIAO/GLOBAL-SOLUTION-2/`, com o `.venv` da raiz.

1. Crie os usuários. A senha é pedida sem eco, tem no mínimo 8 caracteres, fica só em hash scrypt e nunca vai para o Git:
   ```
   python src/operador/autenticacao.py criar transito1 transito "Operador(a) Trânsito 1"
   python src/operador/autenticacao.py criar saude1 saude "Operador(a) Saúde 1"
   python src/operador/autenticacao.py criar gestao1 gestao "Gestão 1"
   python src/operador/autenticacao.py listar
   ```
2. (Opcional) Processe os clipes sintéticos em `data/raw/video/veo3/`. Sem clipes, a câmera usa os vídeos reais
   (Pexels) já anotados:
   ```
   python src/visao/processar_clipes.py
   ```
3. Abra a interface: `streamlit run src/operador/app.py`.

## Perfis

| Perfil | Telas | Pode |
|---|---|---|
| Trânsito | Câmera e ocorrências, Sala de controle | confirmar ou descartar (com motivo), reportar ocorrência, mandar cenário ao nó |
| Saúde | Ocorrências confirmadas, Sala de controle | despachar a ambulância (SIMULADA), encerrar |
| Gestão | Painel, Ocorrências (tempo de cada etapa), Estudo A, Clipes sintéticos, Sala de controle | só lê |

## Segurança

- A senha é guardada em hash scrypt, com sal de 16 bytes por usuário, e comparada em tempo constante.
- Depois de **5 erros**, o usuário fica **bloqueado por 5 min**. A mensagem é a mesma para usuário inexistente e para senha errada.
- A sessão expira com **30 min sem uso**.
- Toda ação confere o perfil no servidor (`perfis.exigir`), não só na tela.
- Entradas, saídas, falhas e bloqueios vão para a tabela `acessos`, sem a senha.
- Cada mudança de ocorrência grava quem fez e quando, na tabela `ocorrencias_historico`.
- LGPD: nenhuma imagem é guardada na ocorrência, só o identificador do clipe. Os vídeos mostrados já saem borrados da visão.

## Ocorrências e despacho

`pendente → confirmada (Trânsito) → despachada (Saúde) → encerrada (Saúde)`, ou `pendente → descartada (Trânsito)`.

A suspeita de acidente vem da regra da visão (`visao.suspeitas_de_queda`, protótipo): pessoa deitada e parada na faixa
ou na pista por 3 s ou mais. A ocorrência nasce **pendente**, e uma pessoa confirma.

Despachar manda ao nó a aproximação da ambulância (600 m a 40 km/h): `eta_s` a cada 10 s e depois `fim`, no mesmo
contrato MQTT da central. Isso foi verificado ao vivo no broker. **Não use a sala de controle junto com `central.py`**:
os comandos dos dois se misturam no nó.

## Testes

```
python -m pytest tests/test_autenticacao.py tests/test_ocorrencias.py tests/test_camera_no.py tests/test_operador_app.py tests/test_queda.py tests/test_processar_clipes.py
```
