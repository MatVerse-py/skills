# Taxonomia canônica MatVerse

Use esta taxonomia para harmonizar `entity_map` e reduzir variação lexical.

## Classes principais

- `person` — pessoas, autores, stakeholders.
- `org` — empresas, times, comunidades.
- `project` — iniciativas, produtos, frentes.
- `artifact` — documento, código, dataset, modelo, pipeline.
- `metric` — KPI, SLI/SLO, indicadores quantitativos.
- `risk` — falhas, vulnerabilidades, dívida técnica, compliance.
- `decision` — escolhas arquiteturais, governança, políticas.
- `time_anchor` — datas, marcos, releases, deadlines.
- `place` — regiões, ambientes, datacenters, mercados.
- `domain_term` — conceitos específicos do domínio.

## Normalização

1. Reduzir caixa e remover pontuação periférica.
2. Singularizar quando aplicável.
3. Aplicar aliases conhecidos (ex.: `LLM Ops` -> `llmops`).
4. Preservar forma original em `mentions[]` para auditoria.

## Regras práticas

- Se uma entidade aparece em >= 3 documentos de tier alto, tratar como hub prioritário.
- Se entidade só aparece em grupos de duplicação, marcar para consolidação.
- Se claim crítico não referencia entidade `artifact` ou `metric`, classificar como baixa evidência.
