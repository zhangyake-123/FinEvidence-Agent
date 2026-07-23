"""Ablation and baseline runner for FinEvidence evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from finevidence.agents.orchestrator import FinEvidenceOrchestrator
from finevidence.agents.retriever_agent import RetrieverAgent, summarize_evidence
from finevidence.evaluation.dataset import load_eval_dataset
from finevidence.evaluation.metrics import evaluate_prediction, summarize_results
from finevidence.evaluation.run_eval import DEFAULT_EVAL_DATASET
from finevidence.indexing.bm25_index import BM25Index, DEFAULT_TEXT_CHUNKS_PATH
from finevidence.indexing.table_retriever import DEFAULT_TABLE_CHUNKS_PATH
from finevidence.indexing.vector_index import VectorIndex


SUPPORTED_MODES = (
    "text_only",
    "vector_text",
    "hybrid_retrieval",
    "hybrid_reranked",
    "full_agent",
    "full_agent_llm_report",
)
DEFAULT_MODES = ("text_only", "vector_text", "hybrid_retrieval", "hybrid_reranked", "full_agent")


def _preview_text(text: str, max_chars: int = 360) -> str:
    return text[:max_chars].replace("\n", " ").strip()


def _text_evidence_summary(record: dict) -> dict:
    return {
        "evidence_type": "text",
        "id": record.get("chunk_id"),
        "score": round(float(record.get("score", 0.0)), 4),
        "ticker": record.get("ticker"),
        "fiscal_year": record.get("fiscal_year"),
        "source_path": record.get("source_path"),
        "section": record.get("section"),
        "text_preview": _preview_text(record.get("text", "")),
    }


def _empty_numeric_report() -> dict:
    return {
        "verifier": "not_applicable",
        "status": "not_applicable",
        "checked_calculations": 0,
        "checked_facts": 0,
        "issue_count": 0,
        "issues": [],
        "calculation_checks": [],
        "fact_checks": [],
    }


def _empty_evidence_report() -> dict:
    return {
        "verifier": "not_applicable",
        "status": "not_applicable",
        "claim_count": 0,
        "supported_count": 0,
        "unsupported_count": 0,
        "ambiguous_count": 0,
        "claim_checks": [],
    }


def _empty_citation_report() -> dict:
    return {
        "verifier": "not_applicable",
        "status": "not_applicable",
        "require_citations": False,
        "citation_count": 0,
        "cited_evidence_count": 0,
        "alias_citations": [],
        "direct_evidence_ids": [],
        "citation_map": {},
        "cited_evidence_ids": [],
        "available_evidence_ids": [],
        "required_evidence_ids": [],
        "unknown_aliases": [],
        "unknown_evidence_ids": [],
        "missing_required_evidence_ids": [],
        "issue_count": 0,
        "issues": [],
    }


def _empty_verifier_report() -> dict:
    return {
        "agent": "not_applicable",
        "status": "not_applicable",
        "claim_count": 0,
        "claims": [],
        "numeric_report": _empty_numeric_report(),
        "evidence_report": _empty_evidence_report(),
        "citation_report": _empty_citation_report(),
        "warnings": [],
    }


def _retrieval_answer(question: str, mode: str, evidence: list[dict]) -> str:
    lines = [
        "## Retrieved Evidence",
        f"Mode: {mode}",
        f"Question: {question}",
        "",
    ]
    if not evidence:
        lines.append("No evidence was retrieved.")
        return "\n".join(lines)

    for index, record in enumerate(evidence, start=1):
        evidence_id = record.get("id")
        evidence_type = record.get("evidence_type", "text")
        score = record.get("score", 0.0)
        lines.extend(
            [
                f"### Evidence {index}: {evidence_id}",
                f"- Type: {evidence_type}",
                f"- Company/year: {record.get('ticker')} {record.get('fiscal_year')}",
                f"- Score: {score}",
            ]
        )
        if evidence_type == "table":
            core_metrics = ", ".join(record.get("core_metrics", [])) or "not detected"
            rows_preview = record.get("rows_preview", [])
            lines.append(f"- Core metrics: {core_metrics}")
            if rows_preview:
                lines.append(f"- Preview rows: {rows_preview}")
        else:
            section = record.get("section") or "unknown section"
            preview = record.get("text_preview") or record.get("content") or ""
            lines.extend(
                [
                    f"- Section: {section}",
                    f"- Preview: {_preview_text(str(preview))}",
                ]
            )
        lines.append("")

    lines.extend(
        [
            "## Note",
            "This baseline retrieves evidence only. It does not extract facts, calculate metrics, or verify claims.",
        ]
    )
    return "\n".join(lines)


def _baseline_prediction(
    mode: str,
    question: str,
    ticker: str | None,
    fiscal_year: int | None,
    evidence: list[dict],
) -> dict:
    numeric_report = _empty_numeric_report()
    evidence_report = _empty_evidence_report()
    verifier_report = _empty_verifier_report()
    citation_report = _empty_citation_report()
    return {
        "agent": f"AblationBaseline:{mode}",
        "mode": mode,
        "question": question,
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "answer": _retrieval_answer(question, mode, evidence),
        "evidence": evidence,
        "claims": [],
        "facts": [],
        "calculations": [],
        "verification_report": numeric_report,
        "evidence_verification_report": evidence_report,
        "citation_report": citation_report,
        "verifier_report": verifier_report,
        "steps": [
            {
                "step": "retrieve_evidence",
                "status": "completed",
                "details": {
                    "mode": mode,
                    "evidence_count": len(evidence),
                },
            },
            {
                "step": "skip_structured_reasoning",
                "status": "completed",
                "details": {
                    "reason": "baseline_retrieval_only",
                },
            },
        ],
        "warnings": ["baseline_retrieval_only"],
    }


class AblationRunner:
    """Run multiple FinEvidence modes against the same evaluation examples."""

    def __init__(
        self,
        text_index: BM25Index,
        vector_index: VectorIndex,
        retriever_agent: RetrieverAgent,
        orchestrator: FinEvidenceOrchestrator,
    ) -> None:
        self.text_index = text_index
        self.vector_index = vector_index
        self.retriever_agent = retriever_agent
        self.orchestrator = orchestrator

    @classmethod
    def from_processed(
        cls,
        text_chunks_path: str | Path = DEFAULT_TEXT_CHUNKS_PATH,
        table_chunks_path: str | Path = DEFAULT_TABLE_CHUNKS_PATH,
        llm_model: str | None = None,
        llm_provider: str | None = None,
        llm_base_url: str | None = None,
    ) -> "AblationRunner":
        return cls(
            text_index=BM25Index.from_jsonl(text_chunks_path),
            vector_index=VectorIndex.from_jsonl(text_chunks_path),
            retriever_agent=RetrieverAgent.from_processed(text_chunks_path, table_chunks_path),
            orchestrator=FinEvidenceOrchestrator.from_processed(
                text_chunks_path,
                table_chunks_path,
                llm_model=llm_model,
                llm_provider=llm_provider,
                llm_base_url=llm_base_url,
            ),
        )

    def run_example(self, example: dict, mode: str, top_k: int = 5) -> dict:
        if mode == "text_only":
            return self._run_text_only(example, top_k=top_k)
        if mode == "vector_text":
            return self._run_vector_text(example, top_k=top_k)
        if mode == "hybrid_retrieval":
            return self._run_hybrid_retrieval(example, top_k=top_k)
        if mode == "hybrid_reranked":
            return self._run_hybrid_reranked(example, top_k=top_k)
        if mode == "full_agent":
            return self.orchestrator.run(
                example["question"],
                ticker=example.get("ticker"),
                fiscal_year=example.get("fiscal_year"),
                top_k=example.get("top_k", top_k),
                report_mode="rule",
            )
        if mode == "full_agent_llm_report":
            return self.orchestrator.run(
                example["question"],
                ticker=example.get("ticker"),
                fiscal_year=example.get("fiscal_year"),
                top_k=example.get("top_k", top_k),
                report_mode="llm",
            )
        raise ValueError(f"Unsupported ablation mode: {mode}")

    def _run_text_only(self, example: dict, top_k: int) -> dict:
        records = self.text_index.search(
            example["question"],
            ticker=example.get("ticker"),
            fiscal_year=example.get("fiscal_year"),
            top_k=example.get("top_k", top_k),
        )
        evidence = [_text_evidence_summary(record) for record in records]
        return _baseline_prediction(
            "text_only",
            example["question"],
            example.get("ticker"),
            example.get("fiscal_year"),
            evidence,
        )

    def _run_vector_text(self, example: dict, top_k: int) -> dict:
        records = self.vector_index.search(
            example["question"],
            ticker=example.get("ticker"),
            fiscal_year=example.get("fiscal_year"),
            top_k=example.get("top_k", top_k),
        )
        evidence = [_text_evidence_summary(record) for record in records]
        return _baseline_prediction(
            "vector_text",
            example["question"],
            example.get("ticker"),
            example.get("fiscal_year"),
            evidence,
        )

    def _run_hybrid_retrieval(self, example: dict, top_k: int) -> dict:
        result = self.retriever_agent.run(
            example["question"],
            ticker=example.get("ticker"),
            fiscal_year=example.get("fiscal_year"),
            top_k=example.get("top_k", top_k),
        )
        evidence = [summarize_evidence(record) for record in result.get("evidence", [])]
        return _baseline_prediction(
            "hybrid_retrieval",
            example["question"],
            example.get("ticker"),
            example.get("fiscal_year"),
            evidence,
        )

    def _run_hybrid_reranked(self, example: dict, top_k: int) -> dict:
        requested_top_k = example.get("top_k", top_k)
        result = self.retriever_agent.run(
            example["question"],
            ticker=example.get("ticker"),
            fiscal_year=example.get("fiscal_year"),
            top_k=requested_top_k,
            rerank=True,
            candidate_k=max(requested_top_k * 3, requested_top_k),
        )
        evidence = [summarize_evidence(record) for record in result.get("evidence", [])]
        return _baseline_prediction(
            "hybrid_reranked",
            example["question"],
            example.get("ticker"),
            example.get("fiscal_year"),
            evidence,
        )


def _validate_modes(modes: list[str]) -> None:
    unsupported = sorted(set(modes) - set(SUPPORTED_MODES))
    if unsupported:
        raise ValueError(f"Unsupported modes: {', '.join(unsupported)}")


def _error_prediction(example: dict, mode: str, error: Exception) -> dict:
    numeric_report = _empty_numeric_report()
    evidence_report = _empty_evidence_report()
    verifier_report = _empty_verifier_report()
    verifier_report["status"] = "failed"
    citation_report = _empty_citation_report()
    return {
        "agent": f"AblationBaseline:{mode}",
        "mode": mode,
        "question": example.get("question"),
        "ticker": example.get("ticker"),
        "fiscal_year": example.get("fiscal_year"),
        "answer": "",
        "evidence": [],
        "claims": [],
        "facts": [],
        "calculations": [],
        "verification_report": numeric_report,
        "evidence_verification_report": evidence_report,
        "citation_report": citation_report,
        "verifier_report": verifier_report,
        "steps": [{"step": "run_mode", "status": "failed", "details": {"mode": mode}}],
        "warnings": [str(error)],
        "error": str(error),
    }


def run_ablation(
    dataset_path: str | Path = DEFAULT_EVAL_DATASET,
    modes: list[str] | None = None,
    text_chunks_path: str | Path = DEFAULT_TEXT_CHUNKS_PATH,
    table_chunks_path: str | Path = DEFAULT_TABLE_CHUNKS_PATH,
    top_k: int = 5,
    llm_model: str | None = None,
    llm_provider: str | None = None,
    llm_base_url: str | None = None,
) -> dict:
    """Run selected ablation modes and return comparable evaluation reports."""

    modes = modes or list(DEFAULT_MODES)
    _validate_modes(modes)

    examples = load_eval_dataset(dataset_path)
    runner = AblationRunner.from_processed(
        text_chunks_path,
        table_chunks_path,
        llm_model=llm_model,
        llm_provider=llm_provider,
        llm_base_url=llm_base_url,
    )
    records_by_mode: dict[str, list[dict]] = {mode: [] for mode in modes}
    summary_by_mode: dict[str, dict] = {}

    for mode in modes:
        for example in examples:
            try:
                prediction = runner.run_example(example, mode=mode, top_k=top_k)
            except Exception as error:  # pragma: no cover - defensive CLI behavior.
                prediction = _error_prediction(example, mode, error)
            evaluation = evaluate_prediction(example, prediction)
            records_by_mode[mode].append(
                {
                    "example": example,
                    "evaluation": evaluation,
                    "prediction": prediction,
                }
            )
        summary_by_mode[mode] = summarize_results(
            [record["evaluation"] for record in records_by_mode[mode]]
        )

    return {
        "dataset": str(dataset_path),
        "modes": modes,
        "summary_by_mode": summary_by_mode,
        "records_by_mode": records_by_mode,
    }


def _compact_records(records: list[dict]) -> list[dict]:
    compact: list[dict] = []
    for record in records:
        evaluation = record["evaluation"]
        compact.append(
            {
                "id": evaluation["id"],
                "question_type": evaluation.get("question_type"),
                "ticker": evaluation.get("ticker"),
                "answer_accuracy": evaluation.get("answer_accuracy"),
                "evidence_recall": evaluation.get("evidence_recall"),
                "numeric_consistency": evaluation.get("numeric_consistency"),
                "hallucination_free": evaluation.get("hallucination_free"),
                "citation_accuracy": evaluation.get("citation_accuracy"),
                "tool_success": evaluation.get("tool_success"),
                "numeric_status": evaluation.get("numeric_status"),
                "evidence_status": evaluation.get("evidence_status"),
                "citation_status": evaluation.get("citation_status"),
                "error": evaluation.get("error"),
            }
        )
    return compact


def compact_result(result: dict) -> dict:
    return {
        **{key: value for key, value in result.items() if key != "records_by_mode"},
        "records_by_mode": {
            mode: _compact_records(records)
            for mode, records in result["records_by_mode"].items()
        },
    }


def summary_result(result: dict) -> dict:
    return {
        "dataset": result["dataset"],
        "modes": result["modes"],
        "summary_by_mode": result["summary_by_mode"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FinEvidence baseline and ablation comparisons.")
    parser.add_argument("--dataset", default=DEFAULT_EVAL_DATASET, help="Path to eval JSONL.")
    parser.add_argument(
        "--modes",
        nargs="+",
        default=list(DEFAULT_MODES),
        choices=SUPPORTED_MODES,
        help="Ablation modes to run.",
    )
    parser.add_argument("--text-chunks", default=DEFAULT_TEXT_CHUNKS_PATH, help="Path to text_chunks.jsonl.")
    parser.add_argument("--tables", default=DEFAULT_TABLE_CHUNKS_PATH, help="Path to table_chunks.jsonl.")
    parser.add_argument("--top-k", type=int, default=5, help="Default top-k retrieval setting.")
    parser.add_argument("--llm-provider", default=None, help="LLM provider for full_agent_llm_report: openai, openai_compatible, or litellm.")
    parser.add_argument("--llm-base-url", default=None, help="Base URL for OpenAI-compatible LLM providers.")
    parser.add_argument("--llm-model", default=None, help="Optional LLM model override for full_agent_llm_report.")
    parser.add_argument("--output", default=None, help="Optional path to save full ablation JSON.")
    parser.add_argument("--records", action="store_true", help="Print compact per-example records.")
    parser.add_argument("--full", action="store_true", help="Print full records instead of compact records.")
    args = parser.parse_args()

    result = run_ablation(
        dataset_path=args.dataset,
        modes=args.modes,
        text_chunks_path=args.text_chunks,
        table_chunks_path=args.tables,
        top_k=args.top_k,
        llm_model=args.llm_model,
        llm_provider=args.llm_provider,
        llm_base_url=args.llm_base_url,
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.full:
        printable = result
    elif args.records:
        printable = compact_result(result)
    else:
        printable = summary_result(result)
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
