---
name: minerador-de-ouros-do-corpus
description: Mine high-value signals from mixed corpora (text, markdown, code, JSON, PDF, and chat), score documents with a 7-component G(d), apply adaptive percentile tiers, and optionally run an LLM oracle (Ollama/HuggingFace/Anthropic mode) for semantic re-ranking.
---

# Minerador de Ouros do Corpus

Use this skill when you need to triage a large corpus and quickly identify the highest-value artifacts for deeper analysis.

## Examples
- Run heuristic scan only: `python scripts/gold_scanner.py /corpus --top 30 --out gold_report.json`
- Run scan with oracle annotations: `python scripts/gold_scanner.py /corpus --oracle --oracle-backend ollama --oracle-model llama3 --oracle-combine annotate --top 20`
- Run scan with Hugging Face API: `HF_TOKEN=... python scripts/gold_scanner.py /corpus --oracle --oracle-backend huggingface --oracle-model openai/gpt-oss-120b --oracle-combine weight --oracle-weight 0.3 --top 20`

## Guidelines
- Keep corpus inputs in a single directory and add extra conversation context with `--chat` files.
- Use `--weights /path/weights.json` to tune score components for your domain.
- Start investigation from `ranking` (tier `gold`) and `exploration_plan`.
- Use `duplication_groups` to consolidate redundant sources before deeper review.
- For oracle mode, install optional deps with `pip install -r requirements-oracle.txt`.
- For local zero-cost inference, run `ollama serve` and pre-pull model with `ollama pull llama3`.
- If Ollama is not available, use `--oracle-backend huggingface` and export `HF_TOKEN`.
