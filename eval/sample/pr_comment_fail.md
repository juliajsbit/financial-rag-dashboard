❌ **LLM eval gate FAILED**

Subset: 2 per category | questions: 8 | source: live

| metric | baseline | current | Δ | status |
| --- | --- | --- | --- | --- |
| faithfulness | 0.984 | 1.000 | +0.017 | 🟢 ok |
| answer_relevancy | 0.609 | 0.763 | +0.154 | 🟢 ok |
| context_precision | 0.595 | 0.667 | +0.071 | 🟢 ok |
| context_recall | 0.464 | 0.583 | +0.119 | 🟢 ok |
| judge_score | 0.944 | 0.825 | -0.119 | 🔴 fail (dropped 0.119 > allowed 0.07) |

_Fails on: faithfulness (drop>0.05 or <0.85), answer_relevancy (drop>0.10 or <0.45), context_precision (drop>0.12 or <0.40), context_recall (drop>0.12 or <0.25), judge_score (drop>0.07 or <0.80)._