"""Shared helpers for the eval harness: dataset loading/validation, paths,
metric configuration, and the regression thresholds used by the CI gate.

Keep this import-light so that `run_eval.py --selftest` and `ci_eval.py` can
run without the heavy RAG / RAGAS dependencies installed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"
GOLDEN_PATH = EVAL_DIR / "golden_dataset.json"
BASELINE_PATH = EVAL_DIR / "baseline_scores.json"

CATEGORIES = ("factual", "comparison", "trend", "refusal")

# Metrics we track end to end. RAGAS metrics + the LLM-judge composite.
TRACKED_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "judge_score",  # mean of the 1-5 LLM-judge scores, normalized to 0-1
)


@dataclass(frozen=True)
class GoldenEntry:
    id: str
    category: str
    question: str
    ground_truth_answer: str
    relevant_tickers: List[str]


def load_golden(path: Path = GOLDEN_PATH) -> List[GoldenEntry]:
    """Load and validate the golden dataset. Raises ValueError on a bad schema."""
    raw = json.loads(path.read_text())
    entries = raw.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("golden_dataset.json: 'entries' must be a non-empty list")

    seen_ids: set[str] = set()
    out: List[GoldenEntry] = []
    for i, e in enumerate(entries):
        for field in ("id", "category", "question", "ground_truth_answer", "relevant_tickers"):
            if field not in e:
                raise ValueError(f"entry #{i} missing required field '{field}'")
        if e["category"] not in CATEGORIES:
            raise ValueError(f"entry {e['id']}: unknown category '{e['category']}'")
        if e["id"] in seen_ids:
            raise ValueError(f"duplicate entry id '{e['id']}'")
        if not isinstance(e["relevant_tickers"], list):
            raise ValueError(f"entry {e['id']}: relevant_tickers must be a list")
        seen_ids.add(e["id"])
        out.append(
            GoldenEntry(
                id=e["id"],
                category=e["category"],
                question=e["question"],
                ground_truth_answer=e["ground_truth_answer"],
                relevant_tickers=list(e["relevant_tickers"]),
            )
        )
    return out


def select_subset(entries: List[GoldenEntry], per_category: int) -> List[GoldenEntry]:
    """Pick up to `per_category` entries from each category, preserving order.

    Used by the CI gate to run a small, representative slice for cost control.
    """
    if per_category <= 0:
        return list(entries)
    picked: List[GoldenEntry] = []
    counts: Dict[str, int] = {c: 0 for c in CATEGORIES}
    for e in entries:
        if counts[e.category] < per_category:
            picked.append(e)
            counts[e.category] += 1
    return picked


def aggregate(per_question: List[dict]) -> Dict[str, float]:
    """Average each tracked metric across questions, ignoring missing values."""
    agg: Dict[str, float] = {}
    for metric in TRACKED_METRICS:
        vals = [
            row["metrics"][metric]
            for row in per_question
            if row.get("metrics", {}).get(metric) is not None
        ]
        if vals:
            agg[metric] = round(sum(vals) / len(vals), 4)
    return agg
