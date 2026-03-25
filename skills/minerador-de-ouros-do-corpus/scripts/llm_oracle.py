#!/usr/bin/env python3
"""LLM oracle evaluator with cache, token-aware truncation, and Ollama support."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore
import urllib.error
import urllib.request

@dataclass
class OracleJudgment:
    scores: Dict[str, float]
    justificativas: Dict[str, str]
    claims_sem_evidencia: List[str]


ORACLE_SYSTEM_PROMPT = """Você é um analista científico especializado em avaliar artefatos técnicos e científicos.

Avalie o documento e atribua notas entre 0 e 1 para:
N=Raridade, F=Formalismo, E=Executabilidade, P=Publicabilidade,
G=Governança, C=Coerência, I=Impacto.

Retorne APENAS JSON válido com os campos:
{
  \"scores\": {\"N\": 0.0, \"F\": 0.0, \"E\": 0.0, \"P\": 0.0, \"G\": 0.0, \"C\": 0.0, \"I\": 0.0},
  \"justificativas\": {\"N\": \"...\", \"F\": \"...\", \"E\": \"...\", \"P\": \"...\", \"G\": \"...\", \"C\": \"...\", \"I\": \"...\"},
  \"claims_sem_evidencia\": [\"...\"]
}
"""


class LLMClient:
    """Provider client supporting Ollama, Hugging Face Inference API, and Anthropic placeholder."""

    def __init__(
        self,
        model: str = "llama3",
        backend: str = "ollama",
        api_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.backend = backend
        self.api_url = api_url.rstrip("/")

    def query(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
        if self.backend == "ollama":
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"num_predict": max_tokens},
            }
            if requests is not None:
                response = requests.post(f"{self.api_url}/api/chat", json=payload, timeout=90)
                response.raise_for_status()
                parsed = response.json()
            else:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.api_url}/api/chat",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=90) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
            return parsed["message"]["content"]

        if self.backend == "anthropic":
            raise NotImplementedError("Backend Anthropic ainda não implementado")

        if self.backend == "huggingface":
            import os

            hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
            if not hf_token:
                raise RuntimeError("HF_TOKEN (ou HUGGINGFACEHUB_API_TOKEN) não definido para backend huggingface.")

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
            }
            # OpenAI-compatible router endpoint for HF Inference Providers.
            response = requests.post(
                "https://router.huggingface.co/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {hf_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=90,
            )
            response.raise_for_status()
            parsed = response.json()
            return parsed["choices"][0]["message"]["content"]

        raise ValueError(f"Backend não suportado: {self.backend}")


def parse_llm_response(response_text: str) -> Optional[OracleJudgment]:
    try:
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not match:
            return None

        data = json.loads(match.group(0))
        if not {"scores", "justificativas", "claims_sem_evidencia"}.issubset(data.keys()):
            return None

        expected_dims = {"N", "F", "E", "P", "G", "C", "I"}
        scores = data["scores"]
        if not expected_dims.issubset(scores.keys()):
            return None

        normalized_scores = {k: max(0.0, min(1.0, float(scores[k]))) for k in expected_dims}
        justificativas = {k: str(data["justificativas"].get(k, "")) for k in expected_dims}
        claims = [str(x) for x in data.get("claims_sem_evidencia", [])][:5]

        return OracleJudgment(
            scores=normalized_scores,
            justificativas=justificativas,
            claims_sem_evidencia=claims,
        )
    except Exception as exc:
        logging.error("Erro ao parsear resposta LLM: %s", exc)
        return None


def _get_tokenizer():
    try:
        import tiktoken  # type: ignore

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def _tokenize_len(text: str, tokenizer) -> int:
    if tokenizer is None:
        return max(1, len(text) // 4)
    return len(tokenizer.encode(text))


def truncate_by_tokens(text: str, max_tokens: int, tokenizer) -> str:
    """Truncate preserving sentence/paragraph boundaries."""
    if _tokenize_len(text, tokenizer) <= max_tokens:
        return text

    if tokenizer is None:
        approx_chars = max_tokens * 4
        truncated = text[:approx_chars]
    else:
        encoded = tokenizer.encode(text)
        truncated = tokenizer.decode(encoded[:max_tokens])

    last_period = truncated.rfind(".")
    last_newline = truncated.rfind("\n")
    cut = max(last_period, last_newline)
    if cut > 0:
        truncated = truncated[: cut + 1]
    return truncated + "\n... [truncado]"


def evaluate_document(
    content: str,
    model: str,
    cost_limit_tokens: int,
    cache_dir: Path,
    backend: str = "ollama",
    api_url: str = "http://localhost:11434",
) -> Optional[OracleJudgment]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    content_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
    cache_file = cache_dir / f"{content_hash}.json"

    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return OracleJudgment(
                scores=data["scores"],
                justificativas=data["justificativas"],
                claims_sem_evidencia=data.get("claims_sem_evidencia", []),
            )
        except Exception:
            pass

    tokenizer = _get_tokenizer()
    truncated = truncate_by_tokens(content, max(300, cost_limit_tokens), tokenizer)
    prompt = f"Documento:\n{truncated}\n\nAvalie conforme as instruções do sistema."

    client = LLMClient(model=model, backend=backend, api_url=api_url)
    try:
        response = client.query(ORACLE_SYSTEM_PROMPT, prompt, max_tokens=1200)
    except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError, NotImplementedError) as exc:
        logging.warning("Falha no oracle (%s): %s", backend, exc)
        return None
    except Exception as exc:
        if requests is not None and isinstance(exc, requests.RequestException):
            logging.warning("Falha no oracle (%s): %s", backend, exc)
            return None
        logging.warning("Falha no oracle (%s): %s", backend, exc)
        return None
    judgment = parse_llm_response(response)
    if not judgment:
        return None

    cache_file.write_text(
        json.dumps(
            {
                "scores": judgment.scores,
                "justificativas": judgment.justificativas,
                "claims_sem_evidencia": judgment.claims_sem_evidencia,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return judgment
