"""LLM-as-judge scoring.

A separate Claude call grades each answer against a rubric and returns strict
JSON. This complements RAGAS: RAGAS is reference-free and metric-specific, the
judge gives a holistic, rubric-anchored read that also handles the "should
refuse" cases (where a good answer is a clear statement of insufficient data).

Run at temperature 0 for repeatability. Scores are 1-5 per dimension; the
harness normalizes the overall score to 0-1 so it sits on the same scale as the
RAGAS metrics.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

RUBRIC = """You are a meticulous evaluator of a financial question-answering assistant.
The assistant must answer ONLY from retrieved context and must refuse or state
"insufficient data" when the context does not support an answer.

Score the assistant's answer on three dimensions, each an integer 1-5:

- accuracy: Are the stated facts correct and consistent with the ground-truth
  answer and the retrieved context? For "refusal" questions, a correct refusal
  or clear statement of insufficient data scores 5; confidently making up an
  answer scores 1.
- completeness: Does the answer address what was asked, with the relevant detail
  (without padding or going beyond the data)?
- citation_quality: Does the answer ground itself in specific data points
  (prices, dates, percentages, sectors) from the context rather than vague
  claims? For refusals, clearly explaining what is missing counts as good
  grounding.

Return STRICT JSON only, no prose, in exactly this shape:
{"accuracy": <1-5>, "completeness": <1-5>, "citation_quality": <1-5>, "rationale": "<one sentence>"}"""


def _build_llm():
    from langchain_anthropic import ChatAnthropic
    from app.core.config import get_settings

    settings = get_settings()
    # Default to Haiku - the judge is one call per question and cheap; keep it so.
    model = os.environ.get("EVAL_JUDGE_MODEL", os.environ.get("EVAL_LLM_MODEL", "claude-haiku-4-5-20251001"))
    return ChatAnthropic(
        model=model,
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0,
        max_tokens=512,
    )


def _user_message(pred: dict) -> str:
    contexts = "\n\n".join(pred["contexts"]) if pred["contexts"] else "(no context retrieved)"
    return (
        f"QUESTION:\n{pred['question']}\n\n"
        f"GROUND-TRUTH ANSWER (reference):\n{pred['ground_truth']}\n\n"
        f"RETRIEVED CONTEXT:\n{contexts}\n\n"
        f"ASSISTANT ANSWER:\n{pred['answer']}\n\n"
        f"Grade the assistant answer per the rubric. JSON only."
    )


def _parse(text: str) -> Dict:
    """Extract the JSON object from the model output, tolerant of stray text."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in judge output: {text[:200]}")
    return json.loads(text[start : end + 1])


def judge_predictions(preds: List[dict]) -> Dict[str, Dict]:
    """Return {prediction_id: {accuracy, completeness, citation_quality,
    overall (1-5), judge_score (0-1), rationale}}.

    On any error returns an empty dict so the harness can still report RAGAS.
    """
    try:
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = _build_llm()
    except Exception as exc:  # pragma: no cover
        print(f"[judge] LLM judge unavailable, skipping: {exc}")
        return {}

    out: Dict[str, Dict] = {}
    for p in preds:
        try:
            resp = llm.invoke([SystemMessage(content=RUBRIC), HumanMessage(content=_user_message(p))])
            parsed = _parse(resp.content if isinstance(resp.content, str) else str(resp.content))
            acc = int(parsed["accuracy"])
            comp = int(parsed["completeness"])
            cite = int(parsed["citation_quality"])
            overall = round((acc + comp + cite) / 3, 3)
            out[p["id"]] = {
                "accuracy": acc,
                "completeness": comp,
                "citation_quality": cite,
                "overall": overall,
                "judge_score": round(overall / 5.0, 4),  # 0-1 scale
                "rationale": parsed.get("rationale", ""),
            }
        except Exception as exc:
            print(f"[judge] failed on {p['id']}: {exc}")
            out[p["id"]] = {"judge_score": None, "error": str(exc)}
    return out
