# Interface do operador BetterWay

Como o sistema seria usado na operação: a câmera da faixa, a fila de ocorrências que o **Trânsito** valida, o despacho
que a **Saúde** recebe e a visão de **Gestão**. A sala de controle mostra o nó ESP32 ao vivo (MQTT).
Spec: [docs/specs/2026-11-17-interface-operador-design.md](../../docs/specs/2026-11-17-interface-operador-design.md).

> **Ambiente de demonstração · sem integração com CET ou SAMU.** A ambulância despachada é SIMULADA; os clipes do
> Veo 3 são SINTÉTICOS e a avaliação deles fica separada dos resultados com dados reais.

## Rodar

Todos os comandos são rodados da raiz do repositório, com o `.venv`.

1. Convide a primeira pessoa da Gestão pelo terminal. O comando imprime um link de uso único, que vale 24 h:
   ```
   python src/operador/autenticacao.py convidar seu.nome@prefeitura.exemplo.org gestao "Seu Nome Completo" --cargo "Coordenação"
   ```
   Abra o link, crie a senha (mínimo de 8 caracteres), leia o QR Code com um aplicativo autenticador (Google ou
   Microsoft Authenticator) e confirme com o primeiro código. Depois, a Gestão convida o resto da equipe pela tela
   **Equipe**. Cada pessoa entra com o próprio e-mail e cuida do seu perfil (foto, nome, telefone, turno, senha) na
   página com o nome dela na barra.
2. (Opcional) Processe os clipes sintéticos em `data/raw/video/veo3/`. Sem clipes, a câmera usa os vídeos reais
   (Pexels) já anotados:
   ```
   python src/visao/processar_clipes.py
   ```
3. Abra a interface: `streamlit run src/operador/app.py`.

## Perfis

| Perfil | Telas | Pode |
|---|---|---|
| Trânsito | Visão geral, Validar ocorrências, Câmeras, Sala de controle, Sobre | confirmar ou descartar (com motivo), reportar ocorrência, mudar o modo do nó |
| Saúde | Visão geral, Atendimentos, Câmeras, Sala de controle, Sobre | despachar a ambulância (SIMULADA), encerrar |
| Gestão | Visão geral, Painel, Câmeras, Ocorrências, Sala de controle, Equipe, Sobre | lê tudo e convida a equipe |

## Segurança

- Conta só por convite da Gestão: link de uso único, vale 24 h e fica guardado apenas como hash (SHA-256). A senha
  nunca é enviada por e-mail; a própria pessoa a cria.
- Dois fatores: senha + código de 6 dígitos de um aplicativo autenticador (TOTP, RFC 6238, implementado em
  `totp.py` com a biblioteca padrão; o QR Code usa `segno`).
- A senha é guardada em hash scrypt, com sal de 16 bytes por usuário, e comparada em tempo constante.
- Depois de **5 erros** (de senha ou de código), o usuário fica **bloqueado por 5 min**. A mensagem é a mesma para usuário inexistente e para senha errada.
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
