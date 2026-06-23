"""Adapter between the eval harness and the production RAG pipeline.

`predict()` runs a question through the real chain in app/services/rag.py and
returns the generated answer plus the exact retrieved contexts, which is what
RAGAS and the LLM judge need.

A fixtures mode (`--fixtures path.json`) replays previously recorded predictions
so the rest of the harness (metrics, judge, reporting, CI compare) can be run
and demonstrated without a live Postgres + Redis stack or API spend.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Make the backend importable: eval/ sits next to backend/.
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class Prediction(dict):
    """{'id', 'question', 'answer', 'contexts': List[str], 'ground_truth', 'category'}"""


def _format_context_docs(docs) -> List[str]:
    """Mirror how rag.format_docs labels each chunk, but keep them as a list
    so RAGAS can score retrieval per-chunk."""
    out = []
    for d in docs:
        meta = d.metadata or {}
        tag = meta.get("ticker", "?")
        when = meta.get("date", meta.get("type", ""))
        out.append(f"[{tag} | {when}]\n{d.page_content}")
    return out


def _predict_live(question: str) -> Dict:
    from app.services.rag import get_rag_chain  # imported lazily

    chain, retriever = get_rag_chain()
    # Use the sync API: langchain-postgres only builds an async engine when given
    # an async driver, so ainvoke() fails on the sync psycopg connection string.
    # Retrieve once for the contexts; the chain retrieves again internally, but
    # this keeps the eval contexts exactly aligned with what we report.
    docs = retriever.invoke(question)
    answer = chain.invoke(question)
    return {"answer": answer, "contexts": _format_context_docs(docs)}


def predict_dataset(
    entries,
    fixtures: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[Prediction]:
    """Run every golden entry through the pipeline (or load fixtures).

    Returns a list of Prediction dicts ready for scoring.
    """
    if limit is not None:
        entries = entries[:limit]

    if fixtures is not None:
        recorded = {p["id"]: p for p in json.loads(Path(fixtures).read_text())}
        preds: List[Prediction] = []
        for e in entries:
            if e.id not in recorded:
                raise KeyError(f"fixtures file missing prediction for id '{e.id}'")
            r = recorded[e.id]
            preds.append(
                Prediction(
                    id=e.id,
                    category=e.category,
                    question=e.question,
                    answer=r["answer"],
                    contexts=r["contexts"],
                    ground_truth=e.ground_truth_answer,
                )
            )
        return preds

    # Trace live runs to LangSmith when configured (no-op without an API key).
    from app.core.tracing import enable_langsmith
    if enable_langsmith("financial-rag-eval"):
        print("[rag] LangSmith tracing enabled")

    preds: List[Prediction] = []
    for e in entries:
        res = _predict_live(e.question)
        preds.append(
            Prediction(
                id=e.id,
                category=e.category,
                question=e.question,
                answer=res["answer"],
                contexts=res["contexts"],
                ground_truth=e.ground_truth_answer,
            )
        )
    return preds


def save_predictions(preds: List[Prediction], path: Path) -> None:
    """Record predictions so they can later be replayed via --fixtures."""
    path.write_text(json.dumps(list(preds), indent=2))
