# FinEvidence Agent LLM Algorithm Plan

## 1. Current Stage

FinEvidence Agent has completed the deterministic end-to-end pipeline:

```text
SEC filings
  -> filing/table parsing
  -> text_chunks.jsonl + table_chunks.jsonl + metric_records.jsonl
  -> BM25 / vector / hybrid retrieval
  -> planner + retriever + table agent + calculator
  -> rule report
  -> numeric / evidence / citation verification
  -> ablation evaluation
```

The project also has an optional LLM report layer:

```text
deterministic evidence + deterministic calculations
  -> LLMReportAgent
  -> final answer with citations
  -> verifier checks
```

The first DeepSeek smoke experiment shows that the LLM connection works, but the
LLM report mode can introduce wording or citation errors. This means the next
stage should not simply add LLM calls everywhere. It should add one LLM module at
a time and prove each module's value with ablation experiments.

## 2. Main Principle

Each LLM-enabled module must answer one experimental question:

```text
Does this module improve a measurable metric without hurting numeric consistency,
citation accuracy, or tool success?
```

Do not connect multiple new LLM modules in one experiment. If planner, reranker,
reporter, and verifier are all changed at the same time, the result cannot explain
which module helped or hurt.

## 3. Module Priority

| Priority | Module | LLM Role | Reason |
| ---: | --- | --- | --- |
| 1 | LLM Evidence Verifier | judge claim-evidence support | Best match with the project theme and later small-model verifier training |
| 2 | LLM Reranker | rerank candidate evidence | Can improve evidence quality before generation |
| 3 | LLM Planner | classify question and extract entities/metrics | Can reduce routing and metric extraction errors |
| 4 | LLM Table Metric Mapper | resolve ambiguous table row labels | Useful for finance-specific metric names and reporting terms |
| 5 | LLM Report Repair | rewrite only failed answer spans | Makes LLM generation safer after verifier checks |

The calculator should stay deterministic. Financial formulas, percentages, and
year-over-year values should be computed by code, not by the LLM.

## 4. Experiment Roadmap

### EXP-002: LLM ReportAgent

Status: implemented, needs full run and failure analysis.

Goal:

```text
Use LLM only to verbalize deterministic evidence and calculation outputs.
```

Hypothesis:

```text
LLM report generation improves risk_summary and trend_analysis answer quality
without lowering numeric consistency or citation accuracy.
```

Command:

```bash
python3 -B -m finevidence.evaluation.ablation \
  --dataset data/eval/qa_v0_1.jsonl \
  --modes full_agent full_agent_llm_report \
  --top-k 5 \
  --records \
  --output reports/ablation_v0_1_llm_report.json
```

Metrics:

| Metric | Expected Direction |
| --- | --- |
| answer_accuracy | up |
| evidence_recall | same |
| numeric_consistency | same |
| citation_accuracy | same or up |
| hallucination_rate | same or down |
| tool_success_rate | same |

Failure analysis checklist:

| Failure Type | What To Inspect |
| --- | --- |
| wrong number wording | Did LLM confuse gross profit amount with gross margin percentage? |
| missing citation | Did LLM use a number without a citation marker? |
| unsupported claim | Did LLM add a business interpretation not present in evidence? |
| schema failure | Did model fail to return valid JSON? |
| over-summary | Did risk answers omit required gold facts? |

Deliverables:

```text
reports/ablation_v0_1_llm_report.json
reports/experiment_report.md EXP-002 section
reports/case_studies.md at least one LLM success and one LLM failure case
```

### EXP-003: LLM Evidence Verifier

Goal:

```text
Use a strong LLM to judge whether each generated claim is supported by retrieved
evidence and citations.
```

This is the most important LLM algorithm step because it directly supports the
project's core claim: reducing hallucinations and unsupported financial answers.

Input:

```json
{
  "question": "...",
  "answer": "...",
  "claim": "...",
  "evidence": [
    {
      "id": "AAPL_2025_10K_table_0014",
      "text": "...",
      "rows": []
    }
  ],
  "calculations": []
}
```

Output:

```json
{
  "label": "supported",
  "confidence": 0.86,
  "supporting_evidence_ids": ["AAPL_2025_10K_table_0014"],
  "reason": "The evidence contains the cited net sales and gross profit values.",
  "suggested_fix": ""
}
```

Labels:

```text
supported
partially_supported
unsupported
contradicted
numeric_error
ambiguous
```

Implementation tasks:

| Task | File |
| --- | --- |
| Add verifier prompt and JSON schema | `finevidence/llm/prompts.py` |
| Add `LLMEvidenceVerifier` | `finevidence/verification/llm_evidence_verifier.py` |
| Add optional mode to `VerifierAgent` | `finevidence/agents/verifier_agent.py` |
| Add ablation mode | `finevidence/evaluation/ablation.py` |
| Add tests with fake LLM client | `tests/test_llm_evidence_verifier.py` |

Suggested ablation modes:

```text
full_agent
full_agent_llm_report
full_agent_llm_verifier
full_agent_llm_report_llm_verifier
```

Metrics:

| Metric | Purpose |
| --- | --- |
| citation_accuracy | whether citations support claims |
| hallucination_rate | whether unsupported claims are caught |
| tool_success_rate | whether verifier can run reliably |
| cost_per_query | how expensive LLM verification is |
| latency | whether verification is practical |

Deliverables:

```text
reports/ablation_v0_1_llm_verifier.json
reports/experiment_report.md EXP-003 section
data/eval/verifier_cases_v0_1.jsonl
```

### EXP-004: LLM Reranker

Goal:

```text
Use an LLM or reranker model to reorder retrieved text/table evidence candidates.
```

The retriever already has BM25, vector, and hybrid modes. The LLM reranker should
not replace retrieval. It should only rerank the top candidates.

Input:

```json
{
  "question": "...",
  "candidates": [
    {
      "id": "...",
      "ticker": "AAPL",
      "fiscal_year": 2025,
      "section": "Item 1A. Risk Factors",
      "text_preview": "..."
    }
  ]
}
```

Output:

```json
{
  "ranked_ids": ["...", "..."],
  "rationales": {
    "...": "This candidate directly discusses supply chain risk."
  }
}
```

Implementation tasks:

| Task | File |
| --- | --- |
| Add LLM reranker prompt/schema | `finevidence/llm/prompts.py` |
| Add optional LLM reranker class | `finevidence/indexing/reranker.py` |
| Add `--reranker llm` or mode flag | `finevidence/agents/retriever_agent.py` |
| Add ablation mode | `finevidence/evaluation/ablation.py` |

Suggested ablation modes:

```text
hybrid_retrieval
hybrid_reranked
hybrid_llm_reranked
full_agent
full_agent_llm_reranked
```

Metrics:

| Metric | Expected Improvement |
| --- | --- |
| evidence_recall | up |
| answer_accuracy | up if evidence was the bottleneck |
| citation_accuracy | up if better evidence is cited |
| latency | worse, must be measured |
| cost_per_query | worse, must be measured |

When to accept this module:

```text
Accept if evidence_recall or answer_accuracy improves enough to justify added
latency and API cost.
```

### EXP-005: LLM Planner

Goal:

```text
Use LLM to classify question type and extract ticker, fiscal year, metrics,
period range, and needed tools.
```

This should be optional. The deterministic planner remains the fallback.

Input:

```json
{
  "question": "Did Apple's gross margin improve from 2023 to 2025?",
  "default_ticker": "AAPL",
  "default_fiscal_year": 2025
}
```

Output:

```json
{
  "question_type": "trend_analysis",
  "ticker": "AAPL",
  "fiscal_year": 2025,
  "periods": [2023, 2024, 2025],
  "requested_metrics": ["gross_profit", "revenue"],
  "requested_calculations": ["gross_margin"],
  "tools": ["retriever_agent", "table_agent", "calculator_agent"]
}
```

Implementation tasks:

| Task | File |
| --- | --- |
| Add LLM planner prompt/schema | `finevidence/llm/prompts.py` |
| Add `LLMPlannerAgent` or mode inside PlannerAgent | `finevidence/agents/planner.py` |
| Add planner mode to orchestrator | `finevidence/agents/orchestrator.py` |
| Add planner ablation mode | `finevidence/evaluation/ablation.py` |

Metrics:

| Metric | Expected Improvement |
| --- | --- |
| answer_accuracy | up for trend/fact questions |
| tool_success_rate | up if planner fixes routing |
| numeric_consistency | up if metric extraction improves |

Risk:

```text
The LLM planner may infer missing ticker/year incorrectly. It must preserve user
provided CLI arguments as higher-priority constraints.
```

### EXP-006: LLM Table Metric Mapper

Goal:

```text
Use LLM only for ambiguous metric-name mapping, not for arithmetic.
```

Example problem:

```text
Question asks for revenue.
Table row says net sales, total net sales, revenues, sales and other operating revenue.
```

Input:

```json
{
  "question_metric": "revenue",
  "candidate_rows": [
    "Net sales",
    "Cost of sales",
    "Gross margin"
  ],
  "table_context": "Consolidated Statements of Operations"
}
```

Output:

```json
{
  "selected_row": "Net sales",
  "canonical_metric": "revenue",
  "confidence": 0.93,
  "reason": "Net sales is Apple's revenue line item in this statement."
}
```

Implementation tasks:

| Task | File |
| --- | --- |
| Add metric mapper prompt/schema | `finevidence/llm/prompts.py` |
| Add optional metric mapper | `finevidence/agents/table_agent.py` |
| Add tests for ambiguous row labels | `tests/test_table_agent.py` |

Acceptance criterion:

```text
Fix known table extraction failures without reducing metric_calc accuracy.
```

## 5. Verifier Dataset Plan

The LLM Evidence Verifier should also generate training data for later small-model
experiments.

### 5.1 Dataset Source

Use predictions from:

```text
full_agent
full_agent_llm_report
```

For each answer:

```text
answer -> claim_extractor -> claim-evidence pairs -> LLM verifier label
```

### 5.2 Dataset Format

```json
{
  "id": "verifier_v0_1_0001",
  "question": "What was Apple gross margin in 2025?",
  "ticker": "AAPL",
  "fiscal_year": 2025,
  "claim": "Apple's gross margin for fiscal year 2025 was 46.91%.",
  "evidence": [
    {
      "id": "AAPL_2025_10K_table_0014",
      "text": "..."
    }
  ],
  "label": "supported",
  "label_source": "llm",
  "model": "deepseek-v4-pro",
  "confidence": 0.91,
  "needs_human_review": false
}
```

### 5.3 Human Review Strategy

Do not manually label everything at first. Review the most useful subset:

| Priority | Cases |
| ---: | --- |
| 1 | LLM verifier low confidence |
| 2 | rule verifier and LLM verifier disagree |
| 3 | examples with numeric_error |
| 4 | trend claims |
| 5 | risk summary claims |

Target:

```text
100-200 reviewed claim-evidence examples for v0.1.
```

## 6. Small-Model Training Plan

This is the next stage after the LLM verifier baseline.

Candidate models:

```text
Qwen2.5-1.5B/3B
Qwen3-1.7B/4B
Llama 3.2 1B/3B
```

Training objective:

```text
Input: question + claim + evidence
Output: supported / partially_supported / unsupported / contradicted / numeric_error
```

Suggested files:

| File | Purpose |
| --- | --- |
| `finevidence/training/build_verifier_dataset.py` | build claim-evidence-label JSONL |
| `finevidence/training/train_lora_verifier.py` | train LoRA or QLoRA verifier |
| `finevidence/training/evaluate_verifier.py` | compare rule, LLM, and small-model verifier |

Evaluation dimensions:

| Dimension | Compare |
| --- | --- |
| accuracy | rule verifier vs LLM verifier vs small model |
| hallucination detection | unsupported claim detection |
| numeric error detection | numeric_error label accuracy |
| latency | response time per claim |
| cost | API cost vs local model cost |

## 7. Report Writing Plan

The final technical report should not only show scores. It should explain why
each module matters.

Required sections:

```text
1. Problem definition
2. Data and parsing pipeline
3. Retrieval architecture
4. Agent workflow
5. Verifier design
6. LLM module design
7. Evaluation dataset
8. Ablation experiments
9. Failure analysis
10. Small-model verifier experiment
11. Limitations and future work
```

At least three case studies:

| Case | Purpose |
| --- | --- |
| Numeric error caught | Show NumericVerifier value |
| Unsupported claim caught | Show EvidenceVerifier value |
| Table-aware retrieval success | Show table retrieval value |
| LLM report failure | Show why verifier/fallback is needed |

## 8. Immediate Next Actions

Recommended next actions in order:

1. Commit the current LLM report and dotenv work.
2. Run full EXP-002 on `qa_v0_1.jsonl`.
3. Add EXP-002 results to `reports/experiment_report.md`.
4. Inspect failed `full_agent_llm_report` examples.
5. Harden LLM report prompt and citation rules.
6. Implement EXP-003 LLM Evidence Verifier.
7. Build `data/eval/verifier_cases_v0_1.jsonl`.
8. Start small-model verifier training only after the verifier dataset is stable.

## 9. Suggested Commit Messages

Current LLM report and dotenv work:

```text
feat(llm): add provider-neutral report generation
```

Detailed planning document:

```text
docs: add llm algorithm experiment plan
```

LLM Evidence Verifier later:

```text
feat(verification): add llm evidence verifier
```

LLM reranker later:

```text
feat(indexing): add llm evidence reranker
```
