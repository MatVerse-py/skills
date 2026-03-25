---
name: minerador-de-ouros-do-corpus
description: Use esta skill para minerar sinais de alto valor em corpora mistos (txt, md, pdf, código, json e chat inline), pontuar documentos com função G(d) de 7 componentes, calibrar thresholds por percentis adaptativos e entregar ranking por tier (ouro/prata/bronze/ruído), mapa de entidades, grupos de duplicação, claims sem evidência e plano de exploração priorizado.
---

# Minerador de Ouros do Corpus

Execute o scanner principal em `scripts/gold_scanner.py` para processar corpus local + chat inline em uma única execução.

## Fluxo mínimo

1. Preparar corpus em diretório único.
2. Executar scanner:
   - `python scripts/gold_scanner.py /caminho/corpus --top 30 --out gold_report.json`
3. Se houver conversa relevante fora do corpus, anexar:
   - `python scripts/gold_scanner.py /caminho/corpus --chat chat.txt --top 20`
4. Ler saída JSON e começar por `exploration_plan` + itens `tier=gold`.

## Recursos opcionais

- PDF: instalar `pypdf` para extrair texto de PDFs.
- Oracle token-aware: instalar `tiktoken` para contagem real de tokens (fallback aproximado sem ele).
- Pesos customizados: usar `--weights /caminho/pesos.json`.

## Modo Oracle (opcional)

Para refinar a triagem com juízo semântico de LLM:

`python scripts/gold_scanner.py /corpus --oracle --oracle-backend ollama --oracle-model llama3 --oracle-api-url http://localhost:11434 --oracle-combine weight --oracle-weight 0.3`

- `--oracle`: ativa avaliação semântica por documento (com cache por hash em `.oracle_cache/`).
- `--oracle-backend`: define backend (`ollama` local ou `anthropic` API).
- `--oracle-api-url`: endpoint do backend (ex.: Ollama local).
- `--oracle-model`: seleciona o modelo no backend.
- `--oracle-cost-limit`: limita tokens por documento com truncamento token-aware.
- `--oracle-combine`: define estratégia de combinação (`substitute`, `weight`, `annotate`).
- `--oracle-weight`: peso do oracle no modo `weight`.

O relatório inclui `oracle_evaluations` com scores por dimensão, justificativas e claims sem evidência.

## Interpretação operacional

- `ranking`: prioridade geral por valor esperado.
- `entity_map`: distribuição de entidades por documento para detecção de hubs temáticos.
- `duplication_groups`: candidatos a consolidação para reduzir redundância.
- `claims_without_evidence`: pontos com potencial de alucinação/afirmação frágil.
- `exploration_plan`: sequência recomendada de leitura e ação.

## Ajustes recomendados

- Se quase tudo cair em `ruído`, reduza `--min-length` e revise pesos.
- Se houver muitos falsos positivos em `gold`, aumente peso de `evidence_density` e `specificity`.
- Se o corpus for técnico, aumente peso de `code_signal`.

## Referências

- Calibração de score: `references/score_calibration.md`
- Taxonomia de entidades: `references/entity_taxonomy.md`
