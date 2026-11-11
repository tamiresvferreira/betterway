# FIAP - Faculdade de Informática e Administração Paulista

<p align="center">
<a href="https://www.fiap.com.br/">
  <img src="../../assets/logo-fiap.png"
       alt="FIAP - Faculdade de Informática e Administração Paulista"
       width="40%">
</a>
</p>

<br>

# Via Segura SP — nós inteligentes de segurança viária para São Paulo

**Global Solution 2026.2 — CitizenTech: tecnologia centrada no cidadão**

## 👩‍🎓 Integrante

- <a href="https://br.linkedin.com/in/tamiresvferreiras">Tamires Vitória Ferreira dos Santos</a> (entrega individual)

## 👩‍🏫 Professores

### Tutor(a)
- <a href="#">Nome do Tutor</a>

### Coordenador(a)
- <a href="https://www.linkedin.com/in/andregodoichiovato/">André Godoi Chiovato</a>

## 📜 Descrição

São Paulo já tem semáforos adaptativos que otimizam o fluxo de carros. O **Via Segura SP** é uma camada de segurança e acessibilidade sobre essa infraestrutura: nós instalados em pontos críticos que veem a via, avisam motoristas e pedestres por placas inteligentes e ajustam o semáforo.

O projeto tem dois estudos:

| | Estudo A — Perturbação urbana | Estudo B — Risco à vida |
|---|---|---|
| Problema | Tempo perdido no trânsito (132 h/ano no pico, TomTom 2025) | Atropelamentos, travessia de idosos e alagamentos |
| Local | Zona sul (corredor a definir) | Av. Celso Garcia — Largo da Concórdia (Brás) |
| Técnica | Simulação SUMO + aprendizado por reforço | DBSCAN + classificador de gravidade + YOLO + ESP32 |

ODS relacionados: 3, 9, 10, 11 e 13.

## 📁 Estrutura de pastas

* **`data/raw/`** bases originais (Infosiga, GeoSampa, CGE). Arquivos grandes não vão para o Git; ver `data/README.md`.
* **`data/processed/`** bases tratadas e o banco SQLite do projeto.
* **`docs/`** documentação, diagramas e `evidencias/` (prints, métricas e vídeos dos testes).
* **`notebooks/`** análise exploratória, agrupamento e modelos.
* **`src/dados/`** carga e limpeza das bases.
* **`src/risco/`** DBSCAN, índice de concentração e classificador de gravidade.
* **`src/visao/`** detecção de pedestres e veículos com YOLO.
* **`src/esp32/`** firmware do nó (Wokwi): semáforo, botão de travessia, buzzer e placa.
* **`src/simulacao/`** cenários SUMO e agente de aprendizado por reforço (Estudo A).
* **`src/central/`** integração: previsão de chuva, regras dos modos, MQTT e banco.
* **`src/dashboard/`** painel em Streamlit.

## 📎 Links e Observações

### 🔗 Links do Projeto

* **Vídeo de entrega (YouTube, não listado)** — a incluir.

### 🧠 Decisões Técnicas

> A preencher ao longo do desenvolvimento.

### 📢 Observações Gerais

* **Participação na Competição:** [x] Sim, aceito participar / [ ] Não vou participar.
* Bases simuladas e resultados esperados estão identificados como tal na documentação.

## 🔧 Como executar o código

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Instruções de cada módulo ficam no README da respectiva pasta em `src/`.

---

## 📋 Licença

<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><p xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/"><a property="dct:title" rel="cc:attributionURL" href="https://github.com/fiap-tutoria/FIAP-PORTFOLIO-AI">TEMPLATE - FIAP PORTFÓLIO AI</a> por <a rel="cc:attributionURL dct:creator" property="cc:attributionName" href="https://fiap.com.br">FIAP</a> está licenciado sobre <a href="http://creativecommons.org/licenses/by/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">Attribution 4.0 International</a>.</p>
