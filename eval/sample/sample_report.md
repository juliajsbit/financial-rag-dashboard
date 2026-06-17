# Eval report - 20260617_092817

- Questions: **37**  |  subset/category: all  |  source: live
- RAGAS: on  |  LLM judge: on

## Aggregate scores (0-1, higher is better)

| metric | score |
| --- | --- |
| faithfulness | 0.984 |
| answer_relevancy | 0.609 |
| context_precision | 0.595 |
| context_recall | 0.464 |
| judge_score | 0.944 |

## By category

| category | faithfulness | answer_relevancy | context_precision | context_recall | judge_score |
| --- | --- | --- | --- | --- | --- |
| factual | 0.975 | 0.688 | 0.917 | 0.625 | 0.933 |
| comparison | 1.000 | 0.275 | 0.688 | 0.562 | 0.858 |
| trend | 0.970 | 0.824 | 0.021 | 0.125 | 1.000 |
| refusal | - | - | - | - | 0.985 |

## Per-question

| id | category | faithfulness | answer_relevancy | context_precision | context_recall | judge_score |
| --- | --- | --- | --- | --- | --- | --- |
| fact-001 | factual | 1.000 | 0.959 | 1.000 | 1.000 | 1.000 |
| fact-002 | factual | - | 0.778 | 1.000 | 0.000 | 0.933 |
| fact-003 | factual | 1.000 | 0.735 | 1.000 | 1.000 | 0.800 |
| fact-004 | factual | 1.000 | 0.482 | 1.000 | 1.000 | 1.000 |
| fact-005 | factual | 1.000 | 0.911 | 1.000 | 1.000 | 1.000 |
| fact-006 | factual | 0.727 | 0.000 | 1.000 | 0.500 | 0.467 |
| fact-007 | factual | 1.000 | 0.852 | 1.000 | 1.000 | 1.000 |
| fact-008 | factual | 1.000 | 0.777 | 1.000 | 1.000 | 1.000 |
| fact-009 | factual | 1.000 | 0.838 | 1.000 | 1.000 | 1.000 |
| fact-010 | factual | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |
| fact-011 | factual | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| fact-012 | factual | 1.000 | 0.928 | 1.000 | 0.000 | 1.000 |
| cmp-001 | comparison | 1.000 | 0.766 | 1.000 | 0.500 | 0.800 |
| cmp-002 | comparison | 1.000 | 0.738 | 1.000 | 1.000 | 1.000 |
| cmp-003 | comparison | 1.000 | 0.000 | 0.500 | 0.500 | 0.933 |
| cmp-004 | comparison | 1.000 | 0.000 | 1.000 | 0.500 | 0.800 |
| cmp-005 | comparison | 1.000 | 0.000 | 1.000 | 1.000 | 0.533 |
| cmp-006 | comparison | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| cmp-007 | comparison | 1.000 | 0.000 | 0.000 | 0.000 | 0.800 |
| cmp-008 | comparison | 1.000 | 0.698 | 1.000 | 1.000 | 1.000 |
| trend-001 | trend | - | 0.845 | 0.000 | 0.000 | 1.000 |
| trend-002 | trend | - | 0.788 | 0.000 | 0.000 | 1.000 |
| trend-003 | trend | - | 0.727 | 0.000 | 0.000 | 1.000 |
| trend-004 | trend | 1.000 | 0.900 | 0.000 | 0.000 | 1.000 |
| trend-005 | trend | 0.909 | 0.803 | 0.167 | 1.000 | 1.000 |
| trend-006 | trend | 1.000 | 0.946 | 0.000 | 0.000 | 1.000 |
| trend-007 | trend | - | 0.661 | 0.000 | 0.000 | 1.000 |
| trend-008 | trend | - | 0.918 | 0.000 | 0.000 | 1.000 |
| refuse-001 | refusal | - | - | - | - | 1.000 |
| refuse-002 | refusal | - | - | - | - | 1.000 |
| refuse-003 | refusal | - | - | - | - | 1.000 |
| refuse-004 | refusal | - | - | - | - | 1.000 |
| refuse-005 | refusal | - | - | - | - | 1.000 |
| refuse-006 | refusal | - | - | - | - | 0.867 |
| refuse-007 | refusal | - | - | - | - | 1.000 |
| refuse-008 | refusal | - | - | - | - | 1.000 |
| refuse-009 | refusal | - | - | - | - | 1.000 |
