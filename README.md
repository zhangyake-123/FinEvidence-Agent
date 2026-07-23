# FinEvidence Agent

FinEvidence Agent is an evidence-grounded financial research agent for public
company filings. It retrieves relevant disclosure evidence, extracts table
metrics, performs deterministic calculations, verifies citations/numbers, and
optionally uses an LLM to write the final answer.

This project does not provide investment advice.

## Current Scope

The current pipeline focuses on SEC 10-K HTML filings for:

- AAPL
- MSFT
- NVDA
- TSLA
- AMZN

Supported workflows:

- Fact QA: revenue, net income, cash flow, assets, liabilities
- Metric calculation: gross margin, operating margin, net margin, revenue growth
- Trend analysis across years
- Risk and business evidence retrieval
- Rule-based and LLM-backed report generation
- Evaluation and ablation experiments

## Project Layout

```text
finevidence/
  data/           Raw filing parsing and table extraction
  indexing/       BM25, TF-IDF vector, hybrid retrieval, reranking
  agents/         Planner, retriever, table, calculator, verifier, reporter
  verification/   Claim, evidence, numeric, and citation checks
  evaluation/     Dataset loading, metrics, eval, ablation
  llm/            Provider-neutral LLM clients and report prompts
  training/       Placeholder for verifier fine-tuning work
  app/            Placeholder for Streamlit demo

data/
  raw/            Downloaded source filings
  processed/      Generated chunks and metric records
  eval/           Evaluation datasets

reports/          Experiment reports and ablation outputs
tests/            Unit tests
```

## Data Artifacts

The main generated files are:

- `data/processed/text_chunks.jsonl`
- `data/processed/table_chunks.jsonl`
- `data/processed/metric_records.jsonl`
- `data/processed/filings_index.jsonl`
- `data/eval/qa_smoke.jsonl`
- `data/eval/qa_v0_1.jsonl`

Large external datasets, such as a full downloaded FinanceBench repository, are
kept local and should not be committed.

## Common Commands

Parse downloaded filings into text chunks:

```bash
python3 -B -m finevidence.data.sec_filing_parser
```

Parse filing tables and metric records:

```bash
python3 -B -m finevidence.data.table_parser
```

Ingest generic text-like files into text chunks:

```bash
python3 -B -m finevidence.data.ingestion.ingestor \
  --input data/raw/sec/filings \
  --output data/processed/text_chunks.jsonl \
  --source-dataset sec
```

Supported ingestion formats in the generic path:

- HTML
- PDF, when `pypdf` is installed
- JSON
- JSONL
- TXT/Markdown

Run BM25 retrieval:

```bash
python3 -B -m finevidence.indexing.bm25_index \
  "risk factors supply chain competition" \
  --ticker AAPL \
  --year 2025 \
  --section "Item 1A" \
  --top-k 3
```

Run the full rule-based agent:

```bash
python3 -B -m finevidence.agents.orchestrator \
  "What was Apple gross margin in 2025?" \
  --ticker AAPL \
  --year 2025 \
  --top-k 5
```

Run the LLM report mode:

```bash
python3 -B -m finevidence.agents.orchestrator \
  "What was Apple gross margin in 2025?" \
  --ticker AAPL \
  --year 2025 \
  --top-k 5 \
  --report-mode llm
```

Run evaluation:

```bash
python3 -B -m finevidence.evaluation.run_eval \
  --dataset data/eval/qa_smoke.jsonl \
  --top-k 5
```

Run ablation summary:

```bash
python3 -B -m finevidence.evaluation.ablation \
  --dataset data/eval/qa_v0_1.jsonl \
  --modes text_only hybrid_retrieval full_agent \
  --top-k 5
```

Run tests:

```bash
python3 -B -m unittest discover -s tests
```

## LLM Configuration

Copy `.env.example` to `.env` and fill in your model provider settings.

Useful variables:

- `FINEVIDENCE_REPORT_MODE`
- `FINEVIDENCE_LLM_PROVIDER`
- `FINEVIDENCE_LLM_MODEL`
- `FINEVIDENCE_LLM_API_KEY`
- `FINEVIDENCE_LLM_BASE_URL`
- `FINEVIDENCE_LLM_JSON_MODE`

For Aliyun-hosted DeepSeek or other OpenAI-compatible APIs, use:

```text
FINEVIDENCE_LLM_PROVIDER=openai_compatible
FINEVIDENCE_LLM_MODEL=<your-model-name>
FINEVIDENCE_LLM_BASE_URL=<your-openai-compatible-base-url>
FINEVIDENCE_LLM_API_KEY=<your-api-key>
```

## Next Cleanup Direction

The next structural improvement should be a generic ingestion layer:

```text
input file or folder
  -> detect file type
  -> parse with a format-specific parser
  -> normalize to a common document schema
  -> chunk into text_chunks.jsonl
```

That should replace dataset-specific parsing paths over time and make PDF, JSON,
JSONL, HTML, TXT, and CSV ingestion easier to maintain.
