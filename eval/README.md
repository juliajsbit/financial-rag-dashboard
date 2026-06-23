# LLM evaluation harness + CI regression gate

Automated evaluation for the RAG pipeline in this repo. Two layers:

1. **Eval harness** - run a golden dataset through the real RAG chain, score every
   answer with RAGAS and an LLM judge, and write a report.
2. **CI regression gate** - run a subset on every PR that touches the prompt or
   retrieval code, compare to a committed baseline, and fail the build if quality
   regresses.

## Why this exists

A RAG system can break silently: a prompt tweak that reads better to a human can
quietly raise the hallucination rate or hurt retrieval. These are not caught by
unit tests, because the output is non-deterministic natural language. This harness
turns answer quality into measurable, regressioned metrics and wires them into CI
so a bad prompt change fails the PR the same way a broken test would.

## The metrics

All scores are 0-1, higher is better.

| metric | what it measures | catches |
| --- | --- | --- |
| **faithfulness** | is every claim in the answer supported by the retrieved context? | hallucination / made-up numbers |
| **answer_relevancy** | does the answer actually address the question asked? | evasive or off-topic answers |
| **context_precision** | are the retrieved chunks relevant and well-ranked? | noisy retrieval |
| **context_recall** | did retrieval surface everything the reference needs? | missing retrieval |
| **judge_score** | holistic 1-5 rubric score (accuracy, completeness, citation quality), normalized to 0-1 | overall quality + correct refusals |

The first four are [RAGAS](https://docs.ragas.io) metrics. **Faithfulness** and
**answer_relevancy** grade the generation; **context_precision** and
**context_recall** grade the retriever. The **judge_score** is a separate
LLM-as-judge call ([judge.py](judge.py)) with an explicit rubric, run at
temperature 0 for repeatability. It is reference-anchored and handles the
"should refuse / not enough data" cases, where a good answer is a clear statement
of insufficient data rather than a fact.

### No OpenAI dependency

RAGAS defaults to OpenAI for both its judge LLM and its embeddings. This harness
overrides both ([metrics.py](metrics.py)): the judge LLM is **Claude** via
`langchain-anthropic`, and embeddings are the same local **MiniLM** model the
production retriever uses. So the eval is consistent with the app and needs only
`ANTHROPIC_API_KEY`.

## Layout

```
eval/
  golden_dataset.json    # 37 Q/A entries: factual, comparison, trend, refusal
  common.py              # dataset load + schema validation, subset, aggregation
  rag_client.py          # calls the real chain -> {answer, contexts}; fixtures replay
  metrics.py             # RAGAS, wired to Claude + MiniLM
  judge.py               # LLM-as-judge rubric -> JSON
  run_eval.py            # Project 1: full run -> results/{ts}.json + .md
  ci_eval.py             # Project 2: subset run -> compare baseline -> pass/fail
  baseline_scores.json   # committed known-good aggregate scores
  requirements.txt       # ragas + datasets (on top of backend/requirements.txt)
  results/               # per-run reports (gitignored)
```

## Golden dataset

37 entries across four categories:

- **factual** - single-ticker lookups (sector, business, latest close, P/E, 52-week range)
- **comparison** - reasoning across two tickers
- **trend** - qualitative read of weekly price history
- **refusal** - insufficient data, out-of-range dates, no speculation, no personal advice

Price-specific reference answers describe the *expected content/behavior* rather
than a fixed dollar figure, because live figures depend on the ingestion date.

## Setup

RAGAS needs **Python 3.10+** (the backend venv is 3.9). Use a separate venv for
the full harness:

```bash
python3.11 -m venv eval/.venv
source eval/.venv/bin/activate
pip install -r backend/requirements.txt -r eval/requirements.txt
```

The harness imports the app, so `backend/.env` must have a real
`ANTHROPIC_API_KEY` and a `DATABASE_URL`, and the data must be ingested
(`docker-compose up -d`, then POST `/api/ingest` for the tickers in the dataset,
or run the ingest snippet from the workflow).

The dataset, judge, and CI compare work on Python 3.9 too - just pass
`--no-ragas`.

## Running Project 1 (the harness)

```bash
cd eval

python run_eval.py --selftest              # validate the dataset, no model calls
python run_eval.py                         # full run against the live stack
python run_eval.py --subset 2              # 2 questions per category (cheaper)
python run_eval.py --no-ragas              # judge only (works on Python 3.9)
```

Writes `results/{timestamp}.json` (machine-readable: aggregate, by-category, and
per-question scores) and `results/{timestamp}.md` (human-readable summary).

### Offline / no-stack demo

Record predictions once, then replay them without Postgres or API spend:

```bash
python run_eval.py --subset 2 --save-fixtures results/preds.json   # one live run
python run_eval.py --fixtures results/preds.json                   # replay + re-score
```

## Running Project 2 (the CI gate)

```bash
cd eval
python ci_eval.py --subset 2               # run subset, compare to baseline
python ci_eval.py --subset 2 --comment-out ci_comment.md   # also write PR comment
```

Exit codes: **0** pass, **2** regression, **1** harness/usage error (including an
empty run where no metrics were produced - it refuses to pass on that).

### Thresholds

Defined in [ci_eval.py](ci_eval.py). Each metric has a `max_drop` (largest
tolerated decrease vs baseline) and a `floor` (absolute minimum):

| metric | max drop | floor |
| --- | --- | --- |
| faithfulness | 0.05 | 0.85 |
| answer_relevancy | 0.10 | 0.45 |
| context_precision | 0.12 | 0.40 |
| context_recall | 0.12 | 0.25 |
| judge_score | 0.07 | 0.80 |

Floors sit below the observed baseline with headroom: the gate runs a small
subset whose aggregate is a noisier estimate of the full baseline, so
answer_relevancy and the context_* metrics (which run conservative here, see
Results) get wider tolerance, while faithfulness and judge_score get tighter
drops.

### Baseline

`baseline_scores.json` holds the known-good aggregate from a full 37-question
run. Refresh it after a reviewed improvement:

```bash
python ci_eval.py --subset 2 --update-baseline
```

In CI, use the **Update Eval Baseline** workflow (manual `workflow_dispatch`),
which runs the harness and commits the new baseline.

## In CI

[`.github/workflows/llm-eval.yml`](../.github/workflows/llm-eval.yml) triggers on
PRs touching `backend/app/services/rag.py`, `prompts/**`, or `eval/**`. It spins
up Postgres (pgvector) + Redis, ingests a small ticker set, runs
`ci_eval.py --subset 2 --no-ragas`, posts the score diff as a PR comment, and
fails the job on regression. Needs the `ANTHROPIC_API_KEY` repo secret.

### Cost

RAGAS is **call-heavy** (it decomposes every answer and context into many
sub-calls), so it dominates spend. To keep runs cheap:

- The harness **defaults to Haiku** for both the RAGAS LLM and the judge
  (override with `EVAL_LLM_MODEL` / `EVAL_JUDGE_MODEL` for a higher-fidelity run).
- The **CI gate is judge-only** (`--no-ragas`): one Haiku call per question plus
  the app's own generation, so a run costs cents. The judge alone still catches
  prompt regressions (it flags fabricated answers and broken refusals).
- The **update-baseline** workflow keeps the full 5-metric RAGAS picture but runs
  it on Haiku, so refreshing the baseline stays cheap.
- Running full RAGAS on a large model (e.g. Sonnet) over the whole dataset is the
  expensive path - do it deliberately, locally, not on every PR.

**Demonstrating it:** open a PR that weakens the system prompt in `rag.py` (e.g.
remove the "use ONLY the provided context" / "say so clearly - do not
hallucinate" lines and tell the model to always give a number). The gate run
fails with a red diff comment; a PR that keeps the guardrails passes. Captured
examples are in [sample/](sample): [pr_comment_pass.md](sample/pr_comment_pass.md)
and [pr_comment_fail.md](sample/pr_comment_fail.md).

## Results

From a full 37-question run (Claude generation + RAGAS on Sonnet, judge on
Haiku). Full report: [sample/sample_report.md](sample/sample_report.md).

| metric | score |
| --- | --- |
| faithfulness | 0.98 |
| answer_relevancy | 0.61 |
| context_precision | 0.60 |
| context_recall | 0.46 |
| judge_score | 0.94 |

**Reading these honestly** (this is the point of the harness):

- **faithfulness 0.98** and **judge_score 0.94** are the headline quality
  signals - answers are grounded and the rubric judge rates them highly,
  including correct refusals (refusals score ~0.99 with the judge).
- **answer_relevancy** and the **context_* metrics are conservative here, by
  design choice, not because retrieval is bad.** Two reasons: (1) to avoid an
  OpenAI dependency, RAGAS uses the same local MiniLM embeddings as the app,
  which score answer/question similarity lower and flag some correct short
  comparison answers as "noncommittal" (0.0); (2) trend questions have
  qualitative reference answers with no extractable claims, so RAGAS
  context_recall/precision against them is near 0 even when the right weekly
  price chunks were retrieved. Refusal questions are excluded from RAGAS
  entirely and measured by the judge.

The takeaway for an eval pipeline: pick metrics that match the question type,
and don't read a single aggregate as "quality". A stronger embedding model would
lift the RAGAS numbers; the trade-off here is zero external API dependency.

## Observability (LangSmith)

Optional tracing to [LangSmith](https://smith.langchain.com) for inspecting and
debugging runs. When `LANGCHAIN_API_KEY` is set in `backend/.env`, every RAG
chain call and judge call is traced - you can see the retrieved context, the
prompt, the model output, latency, and token counts per eval question, grouped
under a project.

```bash
# backend/.env
LANGCHAIN_API_KEY=ls-...            # from https://smith.langchain.com
LANGCHAIN_PROJECT=financial-rag-eval
```

It is a no-op without a key, so the harness runs unchanged. Enabling is wired in
[backend/app/core/tracing.py](../backend/app/core/tracing.py); the live app
traces under `financial-rag-app`, the eval harness under `financial-rag-eval`.

## Compatibility notes

- The harness calls the RAG chain with the **sync** LangChain API.
  `langchain-postgres` only builds an async engine for an async driver, so
  `ainvoke()` fails on the sync `psycopg` connection string.
- On **Python 3.12+** (tested on 3.14), `nest_asyncio` - which RAGAS applies at
  import - breaks `asyncio.wait_for`. [metrics.py](metrics.py) neutralizes it
  before importing RAGAS, since the harness scores from a plain sync context.
