"""Project 1 - LLM eval harness.

Runs the golden dataset through the RAG pipeline, scores each answer with RAGAS
and an LLM judge, and writes a machine-readable result plus a human-readable
markdown summary.

Examples:
  python eval/run_eval.py                      # full run against the live stack
  python eval/run_eval.py --subset 2           # 2 questions per category
  python eval/run_eval.py --fixtures preds.json --no-ragas   # offline demo
  python eval/run_eval.py --selftest           # validate dataset only, no calls
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Dict, List

from common import (
    RESULTS_DIR,
    TRACKED_METRICS,
    CATEGORIES,
    aggregate,
    load_golden,
    select_subset,
)


def selftest() -> int:
    entries = load_golden()
    by_cat: Dict[str, int] = {c: 0 for c in CATEGORIES}
    for e in entries:
        by_cat[e.category] += 1
    print(f"[selftest] golden dataset OK: {len(entries)} entries")
    for c in CATEGORIES:
        print(f"           {c:<11} {by_cat[c]}")
    return 0


def build_rows(preds, ragas_scores, judge_scores) -> List[dict]:
    rows: List[dict] = []
    for p in preds:
        metrics: Dict[str, float] = {}
        metrics.update(ragas_scores.get(p["id"], {}))
        j = judge_scores.get(p["id"], {})
        if "judge_score" in j:
            metrics["judge_score"] = j["judge_score"]
        rows.append(
            {
                "id": p["id"],
                "category": p["category"],
                "question": p["question"],
                "answer": p["answer"],
                "ground_truth": p["ground_truth"],
                "n_contexts": len(p["contexts"]),
                "metrics": metrics,
                "judge_detail": {k: v for k, v in j.items() if k != "judge_score"},
            }
        )
    return rows


def aggregate_by_category(rows: List[dict]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for cat in CATEGORIES:
        cat_rows = [r for r in rows if r["category"] == cat]
        if cat_rows:
            out[cat] = aggregate(cat_rows)
    return out


def write_reports(rows: List[dict], meta: dict) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = meta["timestamp"]
    agg = aggregate(rows)
    by_cat = aggregate_by_category(rows)

    payload = {
        "meta": meta,
        "aggregate": agg,
        "by_category": by_cat,
        "results": rows,
    }
    json_path = RESULTS_DIR / f"{ts}.json"
    json_path.write_text(json.dumps(payload, indent=2))

    md = _markdown_summary(rows, agg, by_cat, meta)
    (RESULTS_DIR / f"{ts}.md").write_text(md)
    return json_path


def _fmt(v) -> str:
    return f"{v:.3f}" if isinstance(v, (int, float)) else "-"


def _markdown_summary(rows, agg, by_cat, meta) -> str:
    lines = [
        f"# Eval report - {meta['timestamp']}",
        "",
        f"- Questions: **{len(rows)}**  |  subset/category: {meta.get('subset', 'all')}  "
        f"|  source: {meta.get('source')}",
        f"- RAGAS: {'on' if meta.get('ragas') else 'off'}  |  LLM judge: "
        f"{'on' if meta.get('judge') else 'off'}",
        "",
        "## Aggregate scores (0-1, higher is better)",
        "",
        "| metric | score |",
        "| --- | --- |",
    ]
    for m in TRACKED_METRICS:
        if m in agg:
            lines.append(f"| {m} | {_fmt(agg[m])} |")
    lines += ["", "## By category", "", "| category | " + " | ".join(TRACKED_METRICS) + " |",
              "| --- | " + " | ".join(["---"] * len(TRACKED_METRICS)) + " |"]
    for cat in CATEGORIES:
        if cat in by_cat:
            cells = [_fmt(by_cat[cat].get(m)) for m in TRACKED_METRICS]
            lines.append(f"| {cat} | " + " | ".join(cells) + " |")

    lines += ["", "## Per-question", "",
              "| id | category | " + " | ".join(TRACKED_METRICS) + " |",
              "| --- | --- | " + " | ".join(["---"] * len(TRACKED_METRICS)) + " |"]
    for r in rows:
        cells = [_fmt(r["metrics"].get(m)) for m in TRACKED_METRICS]
        lines.append(f"| {r['id']} | {r['category']} | " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the LLM eval harness.")
    ap.add_argument("--subset", type=int, default=0,
                    help="entries per category (0 = all)")
    ap.add_argument("--limit", type=int, default=None,
                    help="hard cap on total questions (applied after subset)")
    ap.add_argument("--fixtures", type=Path, default=None,
                    help="replay recorded predictions instead of calling the live stack")
    ap.add_argument("--save-fixtures", type=Path, default=None,
                    help="save live predictions to this path for later replay")
    ap.add_argument("--no-ragas", action="store_true", help="skip RAGAS metrics")
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM judge")
    ap.add_argument("--selftest", action="store_true",
                    help="validate the dataset and exit (no model calls)")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    entries = load_golden()
    if args.subset:
        entries = select_subset(entries, args.subset)

    # Imported here so --selftest needs none of the heavy deps.
    from rag_client import predict_dataset, save_predictions

    print(f"[run] predicting {len(entries) if args.limit is None else min(args.limit, len(entries))} "
          f"question(s) ({'fixtures' if args.fixtures else 'live'})...")
    preds = predict_dataset(entries, fixtures=args.fixtures, limit=args.limit)
    if args.save_fixtures:
        save_predictions(preds, args.save_fixtures)
        print(f"[run] saved predictions -> {args.save_fixtures}")

    ragas_scores: Dict[str, Dict] = {}
    if not args.no_ragas:
        from metrics import compute_ragas
        print("[run] scoring with RAGAS...")
        ragas_scores = compute_ragas(preds)

    judge_scores: Dict[str, Dict] = {}
    if not args.no_judge:
        from judge import judge_predictions
        print("[run] scoring with LLM judge...")
        judge_scores = judge_predictions(preds)

    rows = build_rows(preds, ragas_scores, judge_scores)
    meta = {
        "timestamp": dt.datetime.now().strftime("%Y%m%d_%H%M%S"),
        "n_questions": len(rows),
        "subset": args.subset or "all",
        "source": "fixtures" if args.fixtures else "live",
        "ragas": not args.no_ragas,
        "judge": not args.no_judge,
    }
    json_path = write_reports(rows, meta)
    agg = aggregate(rows)

    print("\n=== Aggregate ===")
    for m in TRACKED_METRICS:
        if m in agg:
            print(f"  {m:<20} {agg[m]:.3f}")
    print(f"\nWrote {json_path}")
    print(f"Wrote {json_path.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
