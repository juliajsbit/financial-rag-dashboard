"""RAGAS metric computation, configured to use Claude as the judge LLM and the
same local MiniLM embeddings the app uses.

This matters: RAGAS defaults to OpenAI for both its LLM and embeddings and will
fail with an auth error if you don't override them. We point it at Claude
(via langchain-anthropic) and HuggingFace embeddings so the harness has no
OpenAI dependency and stays consistent with the production retriever.

Metrics computed (all 0-1, higher is better):
  faithfulness        - is every claim in the answer supported by the context?
                        (the direct hallucination signal)
  answer_relevancy    - does the answer actually address the question?
  context_precision   - are the retrieved chunks relevant / ranked well?
  context_recall      - did retrieval surface everything the reference needs?

RAGAS is imported lazily so the rest of the harness runs without it installed.
"""
from __future__ import annotations

import os
from typing import Dict, List

# Maps our metric names -> the column names RAGAS may emit, across versions.
_COLUMN_ALIASES = {
    "faithfulness": ("faithfulness",),
    "answer_relevancy": ("answer_relevancy", "response_relevancy"),
    "context_precision": (
        "context_precision",
        "llm_context_precision_with_reference",
    ),
    "context_recall": ("context_recall", "llm_context_recall"),
}


def _build_judge_llm():
    from langchain_anthropic import ChatAnthropic
    from app.core.config import get_settings

    settings = get_settings()
    model = os.environ.get("EVAL_LLM_MODEL", "claude-sonnet-4-6")
    return ChatAnthropic(
        model=model,
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0,  # deterministic scoring
    )


def _build_embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def compute_ragas(preds: List[dict]) -> Dict[str, Dict[str, float]]:
    """Score every prediction with RAGAS.

    Returns {prediction_id: {metric: score}}. On any failure (e.g. RAGAS not
    installed) returns an empty dict so the caller can carry on with the judge.
    """
    try:
        from ragas import evaluate, EvaluationDataset
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )
    except Exception as exc:  # pragma: no cover - depends on env
        print(f"[metrics] RAGAS unavailable, skipping RAGAS metrics: {exc}")
        return {}

    samples = [
        {
            "user_input": p["question"],
            "response": p["answer"],
            "retrieved_contexts": p["contexts"],
            "reference": p["ground_truth"],
        }
        for p in preds
    ]
    dataset = EvaluationDataset.from_list(samples)

    llm = LangchainLLMWrapper(_build_judge_llm())
    embeddings = LangchainEmbeddingsWrapper(_build_embeddings())

    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        embeddings=embeddings,
    )

    df = result.to_pandas()
    out: Dict[str, Dict[str, float]] = {}
    for i, p in enumerate(preds):
        row = df.iloc[i]
        scores: Dict[str, float] = {}
        for our_name, aliases in _COLUMN_ALIASES.items():
            for col in aliases:
                if col in df.columns:
                    val = row[col]
                    scores[our_name] = None if _is_nan(val) else round(float(val), 4)
                    break
        out[p["id"]] = scores
    return out


def _is_nan(x) -> bool:
    try:
        return x != x  # NaN is the only value not equal to itself
    except Exception:
        return False
