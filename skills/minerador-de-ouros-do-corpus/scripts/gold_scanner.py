#!/usr/bin/env python3
"""Gold scanner: rank high-value documents from mixed corpora."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List

DEFAULT_WEIGHTS = {
    "information_density": 0.20,
    "novelty": 0.15,
    "specificity": 0.15,
    "evidence_density": 0.20,
    "actionability": 0.10,
    "entity_relevance": 0.10,
    "code_signal": 0.10,
}

TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".log", ".csv", ".json", ".yaml", ".yml", ".toml", ".py", ".js", ".ts", ".sql"}
EVIDENCE_MARKERS = {"fonte", "source", "paper", "estudo", "benchmark", "métrica", "metric", "dados", "dataset", "evidence", "ref"}
ACTION_VERBS = {"fazer", "implementar", "validar", "executar", "priorizar", "ship", "deploy", "build", "measure", "test"}
STOPWORDS = {"the", "a", "an", "de", "da", "do", "e", "o", "a", "em", "para", "com", "que", "of", "to", "in", "on", "and"}
ORACLE_DIMENSION_WEIGHTS = {"N": 0.22, "F": 0.16, "E": 0.16, "P": 0.14, "G": 0.12, "C": 0.10, "I": 0.10}


@dataclass
class Document:
    doc_id: str
    path: str
    text: str
    kind: str


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine high-value documents from a corpus")
    parser.add_argument("corpus", type=Path, help="Path to corpus directory")
    parser.add_argument("--chat", type=Path, action="append", default=[], help="Optional chat file(s)")
    parser.add_argument("--top", type=int, default=30, help="Top-N documents in ranking")
    parser.add_argument("--out", type=Path, default=Path("gold_report.json"), help="Output JSON report")
    parser.add_argument("--weights", type=Path, default=None, help="JSON file with custom component weights")
    parser.add_argument("--min-length", type=int, default=120, help="Minimum chars to keep a document")
    parser.add_argument("--oracle", action="store_true", help="Ativa avaliação por LLM oracle")
    parser.add_argument("--oracle-backend", choices=["ollama", "anthropic"], default="ollama", help="Backend do LLM")
    parser.add_argument("--oracle-api-url", type=str, default="http://localhost:11434", help="URL da API do backend")
    parser.add_argument("--oracle-model", type=str, default="llama3", help="Modelo LLM")
    parser.add_argument("--oracle-cost-limit", type=int, default=4000, help="Máximo de tokens por documento")
    parser.add_argument(
        "--oracle-combine",
        choices=["substitute", "weight", "annotate"],
        default="annotate",
        help="Como combinar scores do oracle com score heurístico",
    )
    parser.add_argument("--oracle-weight", type=float, default=0.5, help="Peso do oracle no modo weight")
    return parser.parse_args()


def load_weights(path: Path | None) -> Dict[str, float]:
    if path is None:
        return DEFAULT_WEIGHTS.copy()
    custom = json.loads(path.read_text(encoding="utf-8"))
    merged = DEFAULT_WEIGHTS.copy()
    merged.update({k: float(v) for k, v in custom.items() if k in merged})
    total = sum(merged.values()) or 1.0
    return {k: v / total for k, v in merged.items()}


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_\-]{2,}", text)]


def read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def read_document(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return read_pdf(path)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore")


def iter_documents(corpus: Path, chats: List[Path], min_length: int) -> List[Document]:
    docs: List[Document] = []
    for file in corpus.rglob("*"):
        if not file.is_file():
            continue
        if file.suffix.lower() not in TEXT_EXTENSIONS and file.suffix.lower() != ".pdf":
            continue
        text = read_document(file).strip()
        if len(text) < min_length:
            continue
        docs.append(Document(doc_id=f"doc:{len(docs)+1}", path=str(file), text=text, kind="corpus"))

    for chat in chats:
        if chat.exists():
            text = chat.read_text(encoding="utf-8", errors="ignore").strip()
            if len(text) >= min_length:
                docs.append(Document(doc_id=f"chat:{len(docs)+1}", path=str(chat), text=text, kind="chat"))
    return docs


def build_tf(docs: List[Document]) -> List[Counter]:
    return [Counter(tokenize(d.text)) for d in docs]


def cosine(c1: Counter, c2: Counter) -> float:
    if not c1 or not c2:
        return 0.0
    inter = set(c1) & set(c2)
    dot = sum(c1[w] * c2[w] for w in inter)
    n1 = math.sqrt(sum(v * v for v in c1.values()))
    n2 = math.sqrt(sum(v * v for v in c2.values()))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * p
    lo, hi = math.floor(idx), math.ceil(idx)
    if lo == hi:
        return ordered[lo]
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def extract_entities(text: str) -> Dict[str, List[str]]:
    entities: Dict[str, List[str]] = defaultdict(list)
    for candidate in re.findall(r"\b[A-Z][A-Za-z0-9_\-]{2,}\b", text):
        c = candidate.strip()
        lc = c.lower()
        if lc in STOPWORDS:
            continue
        if any(ch.isdigit() for ch in c):
            entities["artifact"].append(c)
        elif lc.endswith(("inc", "ltd", "corp")):
            entities["org"].append(c)
        else:
            entities["domain_term"].append(c)

    for date in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text):
        entities["time_anchor"].append(date)

    return {k: sorted(set(v)) for k, v in entities.items() if v}


def component_scores(doc: Document, tf: Counter, global_df: Counter, n_docs: int, avg_tf: Counter) -> Dict[str, float]:
    tokens = tokenize(doc.text)
    unique = set(tokens)
    length = max(len(tokens), 1)

    information_density = min(1.0, len(unique) / (length * 0.65))

    novelty_proxy = 1.0 - cosine(tf, avg_tf)

    numeric_hits = len(re.findall(r"\b\d+(?:[\.,]\d+)?%?\b", doc.text))
    date_hits = len(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", doc.text))
    specificity = min(1.0, (numeric_hits + date_hits) / max(8, length * 0.03))

    evidence_hits = sum(doc.text.lower().count(m) for m in EVIDENCE_MARKERS)
    evidence_density = min(1.0, evidence_hits / max(3, length * 0.02))

    action_hits = sum(doc.text.lower().count(v) for v in ACTION_VERBS)
    actionability = min(1.0, action_hits / max(2, length * 0.015))

    entities = extract_entities(doc.text)
    entity_relevance = min(1.0, sum(len(v) for v in entities.values()) / max(4, length * 0.02))

    code_tokens = len(re.findall(r"[{}();=]|def\s+|class\s+|import\s+", doc.text))
    code_signal = min(1.0, code_tokens / max(8, length * 0.02))

    return {
        "information_density": information_density,
        "novelty": max(0.0, novelty_proxy),
        "specificity": specificity,
        "evidence_density": evidence_density,
        "actionability": actionability,
        "entity_relevance": entity_relevance,
        "code_signal": code_signal,
    }


def assign_tier(score: float, p35: float, p60: float, p85: float) -> str:
    if score >= p85:
        return "gold"
    if score >= p60:
        return "silver"
    if score >= p35:
        return "bronze"
    return "noise"


def build_duplicate_groups(docs: List[Document], tfs: List[Counter], threshold: float = 0.92) -> List[List[str]]:
    parent = list(range(len(docs)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            if cosine(tfs[i], tfs[j]) >= threshold:
                union(i, j)

    groups: Dict[int, List[str]] = defaultdict(list)
    for idx, doc in enumerate(docs):
        groups[find(idx)].append(doc.doc_id)

    return [g for g in groups.values() if len(g) > 1]


def claims_without_evidence(doc: Document) -> List[str]:
    claims = []
    for sentence in re.split(r"(?<=[.!?])\s+", doc.text):
        s = sentence.strip()
        if not s:
            continue
        lower = s.lower()
        strong_claim = any(k in lower for k in ["sempre", "nunca", "garante", "prova", "definitivo", "100%"])
        has_evidence = any(m in lower for m in EVIDENCE_MARKERS) or bool(re.search(r"\[[0-9]+\]|https?://", s))
        if strong_claim and not has_evidence:
            claims.append(s[:220])
    return claims[:5]


def create_exploration_plan(items: List[Dict]) -> List[Dict]:
    plan = []
    for idx, item in enumerate(items[:15], start=1):
        plan.append(
            {
                "priority": idx,
                "doc_id": item["doc_id"],
                "tier": item["tier"],
                "action": "Ler, extrair claims verificáveis e conectar às entidades centrais.",
            }
        )
    return plan


def oracle_score_from_dims(scores: Dict[str, float]) -> float:
    value = 0.0
    for dim, w in ORACLE_DIMENSION_WEIGHTS.items():
        value += w * float(scores.get(dim, 0.0))
    return max(0.0, min(1.0, value))


def main() -> None:
    args = parse_args()
    docs = iter_documents(args.corpus, args.chat, args.min_length)
    if not docs:
        raise SystemExit("Nenhum documento elegível encontrado. Ajuste --min-length ou corpus.")

    weights = load_weights(args.weights)
    tfs = build_tf(docs)
    avg_tf = Counter()
    for tf in tfs:
        avg_tf.update(tf)
    for k in list(avg_tf):
        avg_tf[k] /= max(1, len(docs))

    global_df = Counter()
    for tf in tfs:
        global_df.update(tf.keys())

    ranking = []
    entity_map: Dict[str, Dict[str, List[str]]] = {}
    all_claims = []

    for doc, tf in zip(docs, tfs):
        components = component_scores(doc, tf, global_df, len(docs), avg_tf)
        score = sum(components[k] * weights[k] for k in DEFAULT_WEIGHTS)
        entities = extract_entities(doc.text)
        claim_gaps = claims_without_evidence(doc)
        if claim_gaps:
            for c in claim_gaps:
                all_claims.append({"doc_id": doc.doc_id, "path": doc.path, "claim": c})

        ranking.append(
            {
                "doc_id": doc.doc_id,
                "path": doc.path,
                "kind": doc.kind,
                "score": round(score, 6),
                "components": {k: round(v, 6) for k, v in components.items()},
                "entities": entities,
            }
        )
        entity_map[doc.doc_id] = entities

    scores = [r["score"] for r in ranking]
    p35, p60, p85 = percentile(scores, 0.35), percentile(scores, 0.60), percentile(scores, 0.85)

    for row in ranking:
        row["tier"] = assign_tier(row["score"], p35, p60, p85)

    ranking.sort(key=lambda x: x["score"], reverse=True)

    oracle_evaluations: Dict[str, Dict] = {}
    if args.oracle:
        from llm_oracle import evaluate_document

        oracle_cache = Path(".oracle_cache")
        oracle_cache.mkdir(parents=True, exist_ok=True)
        scan_count = min(args.top, len(ranking))

        for row in ranking[:scan_count]:
            doc = next(d for d in docs if d.doc_id == row["doc_id"])
            judgment = evaluate_document(
                content=doc.text,
                model=args.oracle_model,
                cost_limit_tokens=args.oracle_cost_limit,
                cache_dir=oracle_cache,
                backend=args.oracle_backend,
                api_url=args.oracle_api_url,
            )
            if not judgment:
                continue
            oracle_base = oracle_score_from_dims(judgment.scores)
            heuristic = row["score"]

            if args.oracle_combine == "substitute":
                row["score"] = oracle_base
            elif args.oracle_combine == "weight":
                w = max(0.0, min(1.0, args.oracle_weight))
                row["score"] = round((w * oracle_base) + ((1.0 - w) * heuristic), 6)

            oracle_evaluations[row["doc_id"]] = {
                "model": args.oracle_model,
                "backend": args.oracle_backend,
                "combine_mode": args.oracle_combine,
                "oracle_score": round(oracle_base, 6),
                "scores": judgment.scores,
                "justificativas": judgment.justificativas,
                "claims_sem_evidencia": judgment.claims_sem_evidencia,
            }

        ranking.sort(key=lambda x: x["score"], reverse=True)
        p35, p60, p85 = percentile([r["score"] for r in ranking], 0.35), percentile([r["score"] for r in ranking], 0.60), percentile([r["score"] for r in ranking], 0.85)
        for row in ranking:
            row["tier"] = assign_tier(row["score"], p35, p60, p85)
        scores = [r["score"] for r in ranking]

    top_n = ranking[: args.top]

    report = {
        "summary": {
            "documents": len(docs),
            "weights": weights,
            "adaptive_thresholds": {"p35": p35, "p60": p60, "p85": p85},
            "score_mean": mean(scores),
        },
        "ranking": top_n,
        "entity_map": entity_map,
        "duplication_groups": build_duplicate_groups(docs, tfs),
        "claims_without_evidence": all_claims,
        "exploration_plan": create_exploration_plan(top_n),
        "oracle_evaluations": oracle_evaluations,
    }

    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Relatório salvo em: {args.out}")


if __name__ == "__main__":
    main()
