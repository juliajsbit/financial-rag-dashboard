# Financial RAG Dashboard

[![LLM Eval Gate](https://github.com/juliajsbit/financial-rag-dashboard/actions/workflows/llm-eval.yml/badge.svg)](https://github.com/juliajsbit/financial-rag-dashboard/actions/workflows/llm-eval.yml)

A full-stack retrieval-augmented-generation app over real market data, plus an
**automated LLM evaluation harness** and a **prompt-regression CI gate** built on
top of it.

The eval work is the focus: it shows how to test a non-deterministic LLM feature
with the same rigor as any other production system - measurable quality metrics,
a golden dataset, and a CI gate that blocks regressions.

## What's here

| Layer | Stack | Folder |
| --- | --- | --- |
| RAG backend | FastAPI, LangChain, Claude, Postgres + pgvector, Redis, yfinance | [`backend/`](backend) |
| Frontend | Next.js 14, TypeScript, streaming chat, D3/Recharts | [`frontend/`](frontend) |
| **Eval harness + CI gate** | RAGAS, LLM-as-judge, GitHub Actions | [`eval/`](eval) |

## The RAG app

Q&A over ingested financial data: weekly OHLCV price history and company profiles
pulled from Yahoo Finance, embedded with MiniLM, stored in pgvector, and answered
by Claude with citations. The system prompt constrains answers to retrieved
context and forbids fabricated numbers.

```bash
docker-compose up -d                       # Postgres (pgvector) + Redis
cd backend && cp .env.example .env         # add ANTHROPIC_API_KEY
pip install -r requirements.txt && uvicorn app.main:app --reload
cd ../frontend && npm install && npm run dev
```

Ingest data via `POST /api/ingest` (`{"ticker": "AAPL"}`), then ask questions in
the UI or via `POST /api/chat/stream`.

## Project 1 - LLM eval harness

Runs a 37-question golden dataset through the real RAG chain and scores every
answer:

- **RAGAS**: faithfulness (hallucination), answer relevancy, context precision and
  recall (retrieval quality) - wired to Claude + the app's MiniLM embeddings, no
  OpenAI dependency.
- **LLM-as-judge**: a Claude call with an accuracy / completeness / citation-quality
  rubric, returning JSON at temperature 0.
- **Report**: per-question and aggregate scores as JSON + markdown.

```bash
cd eval
python run_eval.py --selftest     # validate dataset, no model calls
python run_eval.py --subset 2     # run a cheap slice
```

A full 37-question run scores **faithfulness 0.98** and **judge_score 0.94**
(the headline quality signals); the retrieval metrics run conservative by design
(local embeddings, no OpenAI dependency). See
[eval/sample/sample_report.md](eval/sample/sample_report.md) and the metric
discussion in [eval/README.md](eval/README.md#results).

## Project 2 - prompt regression CI gate

Turns the harness into a quality gate. On any PR that touches the prompt or
retrieval code, GitHub Actions runs a golden subset, compares aggregate scores to
a committed baseline, posts a diff table as a PR comment, and **fails the build**
if a metric drops past its threshold or below its floor.

```bash
cd eval
python ci_eval.py --subset 2      # exit 0 = pass, 2 = regression
```

Weaken the system prompt in `backend/app/services/rag.py` and the gate fails;
tighten it and the gate passes. This is shift-left for AI quality - the same
regression discipline as a test suite, applied to LLM output.

### Blocking merges

The workflow failing is only half of it - to actually **block a merge**, `main`
has a branch protection rule that makes the `eval` check a required status check.
A PR whose eval gate is red cannot be merged until it goes green.

Set it up with the GitHub CLI (run once):

```bash
gh api -X PUT repos/<owner>/<repo>/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["eval"] },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```

This is the part most ML candidates skip: wiring an eval into the same
merge-blocking CI flow that gates normal code. Cost is kept low by running the
gate **judge-only** on a small subset with Haiku (see
[eval/README.md](eval/README.md#cost)).

Full details, metrics explanations, thresholds, and offline-demo instructions:
[`eval/README.md`](eval/README.md).
