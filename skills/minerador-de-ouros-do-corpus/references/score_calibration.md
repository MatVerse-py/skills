# Calibração de score (G(d))

## Componentes padrão (7)

`G(d) = Σ wi * ci(d)` com `Σ wi = 1.0`.

Componentes recomendados:

1. `information_density` — razão entre conteúdo útil e texto boilerplate.
2. `novelty` — distância semântica aproximada para o corpus médio.
3. `specificity` — presença de números, datas, identificadores e detalhes concretos.
4. `evidence_density` — frequência de indicadores de evidência (citação, fonte, experimento, métrica).
5. `actionability` — presença de verbos de ação, plano, próximos passos.
6. `entity_relevance` — quantidade e diversidade de entidades canônicas.
7. `code_signal` — sinal técnico em código/config/logs (quando existir).

## Pesos baseline

```json
{
  "information_density": 0.20,
  "novelty": 0.15,
  "specificity": 0.15,
  "evidence_density": 0.20,
  "actionability": 0.10,
  "entity_relevance": 0.10,
  "code_signal": 0.10
}
```

## Thresholds adaptativos

Use percentis do próprio corpus (sem valores fixos universais):

- `gold`: `score >= p85`
- `silver`: `p60 <= score < p85`
- `bronze`: `p35 <= score < p60`
- `noise`: `score < p35`

## Estratégia de ajuste

- Corpus de produto/negócio: subir `actionability`.
- Corpus científico: subir `evidence_density` e `specificity`.
- Corpus de engenharia: subir `code_signal` e `specificity`.
- Corpus de brainstorming: subir `novelty` e reduzir `evidence_density`.

## Sanity checks

- Se `gold` > 25% do corpus: thresholds provavelmente frouxos.
- Se `gold` < 5%: thresholds ou pesos provavelmente rígidos.
- Se ranking topo tem textos curtos e vagos: aumentar penalidade por baixa `information_density`.
