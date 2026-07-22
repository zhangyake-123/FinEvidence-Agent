"""Run FinEvidence evaluation datasets through the orchestrator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from finevidence.agents.orchestrator import FinEvidenceOrchestrator
from finevidence.evaluation.dataset import load_eval_dataset
from finevidence.evaluation.metrics import evaluate_prediction, summarize_results
from finevidence.indexing.bm25_index import DEFAULT_TEXT_CHUNKS_PATH
from finevidence.indexing.table_retriever import DEFAULT_TABLE_CHUNKS_PATH


DEFAULT_EVAL_DATASET = Path("data/eval/qa_smoke.jsonl")


def _run_example(orchestrator: FinEvidenceOrchestrator, example: dict, top_k: int) -> dict:
    try:
        return orchestrator.run(
            example["question"],
            ticker=example.get("ticker"),
            fiscal_year=example.get("fiscal_year"),
            top_k=example.get("top_k", top_k),
        )
    except Exception as error:  # pragma: no cover - kept to make CLI eval robust.
        return {
            "agent": "FinEvidenceOrchestrator",
            "question": example.get("question"),
            "ticker": example.get("ticker"),
            "fiscal_year": example.get("fiscal_year"),
            "answer": "",
            "evidence": [],
            "claims": [],
            "calculations": [],
            "facts": [],
            "steps": [{"step": "run_orchestrator", "status": "failed"}],
            "verification_report": {"status": "not_applicable"},
            "evidence_verification_report": {"status": "not_applicable"},
            "verifier_report": {"status": "failed"},
            "warnings": [str(error)],
            "error": str(error),
        }


def run_eval(
    dataset_path: str | Path = DEFAULT_EVAL_DATASET,
    text_chunks_path: str | Path = DEFAULT_TEXT_CHUNKS_PATH,
    table_chunks_path: str | Path = DEFAULT_TABLE_CHUNKS_PATH,
    top_k: int = 5,
) -> dict:
    """Run all examples in a dataset and return predictions plus metrics."""

    examples = load_eval_dataset(dataset_path)
    orchestrator = FinEvidenceOrchestrator.from_processed(text_chunks_path, table_chunks_path)
    records: list[dict] = []

    for example in examples:
        prediction = _run_example(orchestrator, example, top_k=top_k)
        evaluation = evaluate_prediction(example, prediction)
        records.append(
            {
                "example": example,
                "evaluation": evaluation,
                "prediction": prediction,
            }
        )

    return {
        "dataset": str(dataset_path),
        "summary": summarize_results([record["evaluation"] for record in records]),
        "records": records,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FinEvidence eval and print a metrics report.")
    parser.add_argument("--dataset", default=DEFAULT_EVAL_DATASET, help="Path to eval JSONL.")
    parser.add_argument("--text-chunks", default=DEFAULT_TEXT_CHUNKS_PATH, help="Path to text_chunks.jsonl.")
    parser.add_argument("--tables", default=DEFAULT_TABLE_CHUNKS_PATH, help="Path to table_chunks.jsonl.")
    parser.add_argument("--top-k", type=int, default=5, help="Default top-k retrieval setting.")
    parser.add_argument("--output", default=None, help="Optional path to save full eval JSON.")
    parser.add_argument("--full", action="store_true", help="Print full records instead of compact records.")
    args = parser.parse_args()

    result = run_eval(
        dataset_path=args.dataset,
        text_chunks_path=args.text_chunks,
        table_chunks_path=args.tables,
        top_k=args.top_k,
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    printable = result if args.full else {**result, "records": _compact_records(result["records"])}
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
