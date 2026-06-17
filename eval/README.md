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
| faithfulness | 0.03 | 0.80 |
| answer_relevancy | 0.05 | 0.75 |
| context_precision | 0.05 | 0.70 |
| context_recall | 0.05 | 0.70 |
| judge_score | 0.05 | 0.70 |

### Baseline

`baseline_scores.json` holds the known-good aggregate. It ships with **seed
placeholder** values - generate a real one after a reviewed run:

```bash
python ci_eval.py --subset 2 --update-baseline
```

In CI, use the **Update Eval Baseline** workflow (manual `workflow_dispatch`),
which runs the harness and commits the new baseline.

## In CI

[`.github/workflows/llm-eval.yml`](../.github/workflows/llm-eval.yml) triggers on
PRs touching `backend/app/services/rag.py`, `prompts/**`, or `eval/**`. It spins
up Postgres (pgvector) + Redis, ingests a small ticker set, runs
`ci_eval.py --subset 2`, posts the score diff as a PR comment, and fails the job
on regression. Needs the `ANTHROPIC_API_KEY` repo secret.

**Demonstrating it:** open a PR that weakens the system prompt in `rag.py` (e.g.
remove the "do not hallucinate" / "use ONLY the provided context" lines). The
gate run shows faithfulness dropping and the job fails with a red diff comment. A
PR that tightens the prompt passes.
