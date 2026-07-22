# FinEvidence-Agent Experiment Report

## Experiment Log

| Exp ID | Date | Stage | Dataset | Samples | Command Output | Purpose |
| --- | --- | --- | --- | ---: | --- | --- |
| EXP-001 | 2026-07-22 | Rule-based baseline | `data/eval/qa_v0_1.jsonl` | 30 | `reports/ablation_v0_1_baseline.json` | Establish a deterministic retrieval + table + calculation + verification baseline before adding LLM generation. |

Command:

```bash
python3 -B -m finevidence.evaluation.ablation \
  --dataset data/eval/qa_v0_1.jsonl \
  --modes text_only vector_text hybrid_retrieval hybrid_reranked full_agent \
  --top-k 5 \
  --output reports/ablation_v0_1_baseline.json
```

## EXP-001 Summary

| Mode | Count | Answer Accuracy | Evidence Recall | Numeric Consistency | Citation Accuracy | Hallucination Rate | Tool Success Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `text_only` | 30 | 0.2000 | 0.2000 | 0.2000 | N/A | 0.0000 | 1.0000 |
| `vector_text` | 30 | 0.1667 | 0.0500 | 0.2000 | N/A | 0.0000 | 1.0000 |
| `hybrid_retrieval` | 30 | 0.2000 | 0.8833 | 0.2000 | N/A | 0.0000 | 1.0000 |
| `hybrid_reranked` | 30 | 0.2000 | 0.9667 | 0.2000 | N/A | 0.0000 | 1.0000 |
| `full_agent` | 30 | 0.7667 | 0.8833 | 0.8333 | 0.9667 | 0.0000 | 0.9667 |

## Full Agent Breakdown

| Question Type | Count | Answer Accuracy | Evidence Recall | Numeric Consistency | Citation Accuracy | Tool Success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `fact_qa` | 8 | 0.8750 | 0.7500 | 0.8750 | 1.0000 | 1.0000 |
| `metric_calc` | 8 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `risk_summary` | 6 | 0.8333 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `trend_analysis` | 8 | 0.3750 | 0.8125 | 0.5000 | 0.8750 | 0.8750 |

## Observations

| Finding | Evidence | Implication |
| --- | --- | --- |
| Hybrid retrieval improves evidence coverage. | `hybrid_reranked` evidence recall is 0.9667, much higher than `text_only` at 0.2000 and `vector_text` at 0.0500. | The retrieval layer is useful and should remain in the LLM pipeline. |
| Rule-based full agent is a strong baseline for calculation questions. | `metric_calc` reaches 1.0000 across answer accuracy, evidence recall, numeric consistency, and citation accuracy. | The calculator/verifier path should stay deterministic even after LLM integration. |
| Trend questions are the main weakness. | `trend_analysis` answer accuracy is 0.3750 and numeric consistency is 0.5000. | The next model layer should focus on interpreting multi-period calculations and answering comparative trend wording. |
| Risk summaries need generation, not only retrieval display. | `risk_summary` evidence recall is 1.0000, but answer accuracy is 0.8333. | LLM report generation should improve natural-language risk summaries while preserving citations. |
| Some fact extraction errors remain. | Example: `finqa_v0_1_003` selects NVIDIA `cost of revenue` as revenue. | Table metric selection needs stricter row-label matching, but this can be handled after the first LLM report experiment. |

## Next Experiment

| Exp ID | Planned Change | Hypothesis | Main Metrics |
| --- | --- | --- | --- |
| EXP-002 | Add `LLMReportAgent` while keeping retrieval, table extraction, calculation, and verification deterministic. | LLM generation should improve `risk_summary` and `trend_analysis` answer accuracy without hurting numeric consistency or citation accuracy. | `answer_accuracy`, `numeric_consistency`, `citation_accuracy`, `hallucination_rate` |
