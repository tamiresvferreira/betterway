# Painel (Streamlit)

Mapa de risco, indicadores de todos os módulos e eventos/alertas ao vivo. **Só lê** o que já existe (banco
`data/processed/seguranca_viaria.db` e `docs/evidencias/`), para os números baterem com o PDF.

**Estado (17/11/2026):** funcionando; teste em `tests/test_dashboard.py` (abre o painel com um banco de exemplo e sem
banco). Capturas em `docs/evidencias/painel_*.png`.

## Como rodar (de `1TIAO/GLOBAL-SOLUTION-2`)

```bash
../../.venv/Scripts/python.exe -m streamlit run src/dashboard/app.py
```

Para ver os alertas chegando: com o nó aberto no Wokwi, rode em outros terminais `src/central/gravador_mqtt.py` e
`src/central/central.py` (demonstração); a aba "Eventos e alertas" atualiza a cada 5 s.

## Abas

| Aba | Conteúdo | Fonte |
|---|---|---|
| Mapa de risco | Grupos do DBSCAN (tamanho = peso; vermelho = 50 primeiros do ranking urbano; anel = piloto) e os 10 primeiros | tabela `clusters` |
| Indicadores | Modelo de risco (notebook 06), visão (07 e 09, DEMONSTRAÇÃO), aceitação do nó ESP32, Estudo A (RESULTADOS ESPERADOS) | `docs/evidencias/` |
| Eventos e alertas | Últimos alertas da central e eventos (visão, ESP32, central), com filtro por origem | tabelas `alertas` e `eventos` |

Outro banco: variável de ambiente `VIA_SEGURA_DB`.
