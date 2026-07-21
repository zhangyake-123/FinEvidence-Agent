"""Retriever agent wrapper around the hybrid retriever."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from finevidence.indexing.bm25_index import DEFAULT_TEXT_CHUNKS_PATH
from finevidence.indexing.hybrid_retriever import HybridRetriever
from finevidence.indexing.table_retriever import DEFAULT_TABLE_CHUNKS_PATH


def _preview_text(text: str, max_chars: int = 260) -> str:
    return text[:max_chars].replace("\n", " ")


def _preview_rows(rows: list[list[str]], max_rows: int = 5) -> list[list[str]]:
    preview: list[list[str]] = []
    for row in rows:
        cleaned = [str(cell).strip() for cell in row]
        if any(cleaned):
            preview.append(cleaned)
        if len(preview) >= max_rows:
            break
    return preview


def summarize_evidence(record: dict) -> dict:
    """Return a compact evidence summary for logs and CLI output."""

    summary = {
        "evidence_type": record.get("evidence_type"),
        "id": record.get("id"),
        "score": round(float(record.get("score", 0.0)), 4),
        "ticker": record.get("ticker"),
        "fiscal_year": record.get("fiscal_year"),
        "source_path": record.get("source_path"),
    }
    if "retrieval_score" in record:
        summary["retrieval_score"] = round(float(record.get("retrieval_score", 0.0)), 4)
    if "rerank_score" in record:
        summary["rerank_score"] = round(float(record.get("rerank_score", 0.0)), 4)
    if "rerank_features" in record:
        summary["rerank_features"] = record.get("rerank_features", {})
    if record.get("evidence_type") == "text":
        summary["section"] = record.get("section")
        summary["text_preview"] = _preview_text(record.get("content", ""))
    elif record.get("evidence_type") == "table":
        summary["table_index"] = record.get("table_index")
        summary["core_metrics"] = record.get("core_metrics", [])
        summary["rows_preview"] = _preview_rows(record.get("rows", []))
    return summary


class RetrieverAgent:
    """Deterministic retrieval tool for the agent workflow."""

    def __init__(self, retriever: HybridRetriever) -> None:
        self.retriever = retriever

    @classmethod
    def from_processed(
        cls,
        text_path: str | Path = DEFAULT_TEXT_CHUNKS_PATH,
        table_path: str | Path = DEFAULT_TABLE_CHUNKS_PATH,
    ) -> "RetrieverAgent":
        return cls(HybridRetriever.from_jsonl(text_path, table_path))

    def run(
        self,
        question: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_k: int = 8,
        rerank: bool = False,
        candidate_k: int | None = None,
    ) -> dict:
        """Retrieve evidence candidates for a question."""

        evidence = self.retriever.retrieve(
            question,
            ticker=ticker,
            fiscal_year=fiscal_year,
            top_k=top_k,
            rerank=rerank,
            candidate_k=candidate_k,
        )
        return {
            "agent": "RetrieverAgent",
            "question": question,
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "rerank": rerank,
            "candidate_k": candidate_k,
            "evidence_count": len(evidence),
            "evidence": evidence,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RetrieverAgent.")
    parser.add_argument("question", help="Question to retrieve evidence for.")
    parser.add_argument("--ticker", default=None, help="Optional ticker filter, e.g. AAPL.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year filter.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of evidence records.")
    parser.add_argument("--text-chunks", default=DEFAULT_TEXT_CHUNKS_PATH, help="Path to text_chunks.jsonl.")
    parser.add_argument("--tables", default=DEFAULT_TABLE_CHUNKS_PATH, help="Path to table_chunks.jsonl.")
    parser.add_argument("--rerank", action="store_true", help="Apply rule-based evidence reranking.")
    parser.add_argument("--candidate-k", type=int, default=None, help="Number of initial candidates before reranking.")
    parser.add_argument("--full", action="store_true", help="Print full evidence records instead of summaries.")
    args = parser.parse_args()

    agent = RetrieverAgent.from_processed(args.text_chunks, args.tables)
    result = agent.run(
        args.question,
        ticker=args.ticker,
        fiscal_year=args.year,
        top_k=args.top_k,
        rerank=args.rerank,
        candidate_k=args.candidate_k,
    )
    if not args.full:
        result = {
            **{key: value for key, value in result.items() if key != "evidence"},
            "evidence": [summarize_evidence(record) for record in result["evidence"]],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
