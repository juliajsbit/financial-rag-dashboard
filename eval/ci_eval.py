"""Project 2 - prompt regression CI gate.

Runs the eval harness on a representative subset, compares the new aggregate
scores against a committed baseline, and FAILS (exit 2) if any metric regresses
beyond its allowed drop or falls below its floor. Writes a markdown diff table
suitable for posting as a PR comment.

Exit codes: 0 = pass, 2 = regression, 1 = harness/usage error.

Examples:
  python eval/ci_eval.py --subset 2
  python eval/ci_eval.py --fixtures eval/results/preds.json --no-ragas   # offline
  python eval/ci_eval.py --update-baseline --subset 2                    # refresh baseline
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Dict, Optional

from common import BASELINE_PATH, TRACKED_METRICS, aggregate, load_golden, select_subset

# Regression policy. max_drop = largest tolerated decrease vs baseline.
# floor = absolute minimum acceptable score regardless of baseline.
#
# Floors are set below the observed full-dataset baseline with headroom, because
# the gate runs a small SUBSET (cost control) whose aggregate is a noisier
# estimate of the full baseline. faithfulness and judge_score are the headline
# quality metrics and get tighter drops; answer_relevancy and the context_*
# metrics run conservative under local MiniLM embeddings + qualitative
# references, so they get wider tolerance (see eval/README.md).
THRESHOLDS: Dict[str, Dict[str, float]] = {
    "faithfulness": {"max_drop": 0.05, "floor": 0.85},
    "answer_relevancy": {"max_drop": 0.10, "floor": 0.45},
    "context_precision": {"max_drop": 0.12, "floor": 0.40},
    "context_recall": {"max_drop": 0.12, "floor": 0.25},
    "judge_score": {"max_drop": 0.07, "floor": 0.80},
}


def load_baseline(path: Path = BASELINE_PATH) -> Dict[str, float]:
    data = json.loads(path.read_text())
    return data.get("metrics", {})


def run_harness(args) -> Dict:
    """Run predictions + scoring and return the per-question rows + aggregate."""
    from run_eval import build_rows

    entries = load_golden()
    if args.subset:
        entries = select_subset(entries, args.subset)

    from rag_client import predict_dataset

    preds = predict_dataset(entries, fixtures=args.fixtures, limit=args.limit)

    ragas_scores: Dict = {}
    if not args.no_ragas:
        from metrics import compute_ragas
        ragas_scores = compute_ragas(preds)

    judge_scores: Dict = {}
    if not args.no_judge:
        from judge import judge_predictions
        judge_scores = judge_predictions(preds)

    rows = build_rows(preds, ragas_scores, judge_scores)
    return {"rows": rows, "aggregate": aggregate(rows), "n": len(rows)}


def evaluate_gate(current: Dict[str, float], baseline: Dict[str, float]):
    """Return (passed: bool, findings: list[dict]) for each tracked metric."""
    findings = []
    passed = True
    for m in TRACKED_METRICS:
        cur = current.get(m)
        base = baseline.get(m)
        th = THRESHOLDS.get(m, {})
        status = "ok"
        note = ""
        if cur is None:
            status = "missing"
            note = "metric not produced this run"
        else:
            delta = None if base is None else round(cur - base, 4)
            if "floor" in th and cur < th["floor"]:
                status = "fail"
                note = f"below floor {th['floor']:.2f}"
                passed = False
            elif delta is not None and "max_drop" in th and delta < -th["max_drop"]:
                status = "fail"
                note = f"dropped {abs(delta):.3f} > allowed {th['max_drop']:.2f}"
                passed = False
            findings.append(
                {"metric": m, "current": cur, "baseline": base,
                 "delta": delta, "status": status, "note": note}
            )
            continue
        findings.append(
            {"metric": m, "current": cur, "baseline": base,
             "delta": None, "status": status, "note": note}
        )
    return passed, findings


def render_comment(passed: bool, findings, meta: Dict) -> str:
    head = "✅ **LLM eval gate passed**" if passed else "❌ **LLM eval gate FAILED**"
    lines = [
        head,
        "",
        f"Subset: {meta.get('subset')} per category | questions: {meta.get('n')} | "
        f"source: {meta.get('source')}",
        "",
        "| metric | baseline | current | Δ | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for f in findings:
        base = f"{f['baseline']:.3f}" if isinstance(f["baseline"], (int, float)) else "-"
        cur = f"{f['current']:.3f}" if isinstance(f["current"], (int, float)) else "-"
        if isinstance(f["delta"], (int, float)):
            delta = f"{f['delta']:+.3f}"
        else:
            delta = "-"
        icon = {"ok": "🟢", "fail": "🔴", "missing": "⚪"}.get(f["status"], "")
        suffix = f" ({f['note']})" if f["note"] else ""
        lines.append(f"| {f['metric']} | {base} | {cur} | {delta} | {icon} {f['status']}{suffix} |")
    rules = ", ".join(
        f"{m} (drop>{THRESHOLDS[m]['max_drop']:.2f} or <{THRESHOLDS[m]['floor']:.2f})"
        for m in TRACKED_METRICS if m in THRESHOLDS
    )
    lines += ["", f"_Fails on: {rules}._"]
    return "\n".join(lines)


def update_baseline(aggregate_scores: Dict[str, float], meta: Dict, path: Path = BASELINE_PATH) -> None:
    payload = {
        "_comment": "Produced by eval/ci_eval.py --update-baseline from a reviewed run.",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_questions": meta.get("n"),
        "source": meta.get("source"),
        "metrics": aggregate_scores,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"[ci] baseline updated -> {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="LLM eval regression gate.")
    ap.add_argument("--subset", type=int, default=2, help="entries per category")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--fixtures", type=Path, default=None)
    ap.add_argument("--no-ragas", action="store_true")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--comment-out", type=Path, default=None,
                    help="write the PR-comment markdown to this path")
    ap.add_argument("--update-baseline", action="store_true",
                    help="run, then overwrite the baseline with the new scores")
    args = ap.parse_args()

    result = run_harness(args)
    current = result["aggregate"]
    meta = {
        "subset": args.subset or "all",
        "n": result["n"],
        "source": "fixtures" if args.fixtures else "live",
    }

    if args.update_baseline:
        update_baseline(current, meta)
        return 0

    if not current:
        print("[ci] ERROR: no metrics were produced (RAGAS and judge both empty). "
              "Refusing to pass the gate on an empty run.")
        return 1

    baseline = load_baseline()
    passed, findings = evaluate_gate(current, baseline)
    comment = render_comment(passed, findings, meta)
    print("\n" + comment + "\n")
    if args.comment_out:
        args.comment_out.write_text(comment)
        print(f"[ci] wrote PR comment -> {args.comment_out}")

    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
