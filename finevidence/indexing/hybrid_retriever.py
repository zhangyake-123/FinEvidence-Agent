"""Hybrid retrieval over text chunks and financial tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from finevidence.indexing.bm25_index import BM25Index, DEFAULT_TEXT_CHUNKS_PATH, tokenize
from finevidence.indexing.reranker import EvidenceReranker
from finevidence.indexing.table_retriever import DEFAULT_TABLE_CHUNKS_PATH, TableRetriever


TEXT_QUERY_TERMS = {
    "business",
    "competition",
    "competitive",
    "customer",
    "customers",
    "legal",
    "management",
    "market",
    "md",
    "mda",
    "regulation",
    "regulatory",
    "risk",
    "risks",
    "section",
    "strategy",
    "supplier",
    "suppliers",
    "supply",
    "chain",
}

TABLE_QUERY_TERMS = {
    "assets",
    "balance",
    "cash",
    "cost",
    "debt",
    "equity",
    "expenses",
    "flow",
    "gross",
    "income",
    "liabilities",
    "margin",
    "net",
    "operating",
    "profit",
    "revenue",
    "sales",
    "statement",
}

RISK_SECTION_TERMS = {"risk", "risks", "risk factors", "supply chain", "competition"}
BUSINESS_SECTION_TERMS = {"business", "strategy", "customers", "products", "services"}
MDA_SECTION_TERMS = {"management discussion", "md&a", "mda", "results of operations"}


def classify_query(query: str) -> str:
    """Classify query routing needs as text, table, or mixed."""

    query_lower = query.lower()
    query_terms = set(tokenize(query))
    text_hits = len(query_terms & TEXT_QUERY_TERMS)
    table_hits = len(query_terms & TABLE_QUERY_TERMS)

    if any(phrase in query_lower for phrase in ("income statement", "balance sheet", "cash flow")):
        table_hits += 3
    if any(phrase in query_lower for phrase in ("risk factors", "supply chain", "legal proceedings")):
        text_hits += 3

    if table_hits and text_hits:
        return "mixed"
    if table_hits:
        return "table"
    return "text"


def infer_text_section(query: str) -> str | None:
    """Infer a helpful 10-K section filter for clearly textual questions."""

    query_lower = query.lower()
    if any(term in query_lower for term in RISK_SECTION_TERMS):
        return "Item 1A"
    if any(term in query_lower for term in BUSINESS_SECTION_TERMS):
        return "Item 1."
    if any(term in query_lower for term in MDA_SECTION_TERMS):
        return "Item 7"
    return None


def _weights(query_type: str) -> tuple[float, float]:
    if query_type == "table":
        return 0.55, 1.0
    if query_type == "text":
        return 1.0, 0.45
    return 0.85, 0.85


def _search_sizes(query_type: str, top_k: int) -> tuple[int, int]:
    if query_type == "table":
        return max(2, top_k // 2), top_k
    if query_type == "text":
        return top_k, 0
    return top_k, top_k


def _text_evidence(record: dict, weight: float) -> dict:
    raw_score = float(record.get("score", 0.0))
    return {
        "evidence_type": "text",
        "id": record.get("chunk_id"),
        "score": raw_score * weight,
        "raw_score": raw_score,
        "weight": weight,
        "ticker": record.get("ticker"),
        "fiscal_year": record.get("fiscal_year"),
        "filing_type": record.get("filing_type"),
        "section": record.get("section"),
        "content": record.get("text", ""),
        "source_path": record.get("source_path"),
    }


def _table_evidence(record: dict, weight: float) -> dict:
    raw_score = float(record.get("score", 0.0))
    return {
        "evidence_type": "table",
        "id": record.get("table_id"),
        "score": raw_score * weight,
        "raw_score": raw_score,
        "weight": weight,
        "ticker": record.get("ticker"),
        "fiscal_year": record.get("fiscal_year"),
        "filing_type": record.get("filing_type"),
        "table_index": record.get("table_index"),
        "columns": record.get("columns", []),
        "rows": record.get("rows", []),
        "core_metrics": record.get("core_metrics", []),
        "source_path": record.get("source_path"),
    }


class HybridRetriever:
    """Unified retrieval interface over text and table evidence."""

    def __init__(
        self,
        text_index: BM25Index,
        table_retriever: TableRetriever,
        reranker: EvidenceReranker | None = None,
    ) -> None:
        self.text_index = text_index
        self.table_retriever = table_retriever
        self.reranker = reranker or EvidenceReranker()

    @classmethod
    def from_jsonl(
        cls,
        text_path: str | Path = DEFAULT_TEXT_CHUNKS_PATH,
        table_path: str | Path = DEFAULT_TABLE_CHUNKS_PATH,
    ) -> "HybridRetriever":
        return cls(
            text_index=BM25Index.from_jsonl(text_path),
            table_retriever=TableRetriever.from_jsonl(table_path),
        )

    def retrieve(
        self,
        query: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_k: int = 8,
        rerank: bool = False,
        candidate_k: int | None = None,
    ) -> list[dict]:
        """Retrieve ranked text and table evidence candidates."""

        query_type = classify_query(query)
        text_weight, table_weight = _weights(query_type)
        retrieval_k = max(top_k, candidate_k or top_k * 3) if rerank else top_k
        text_top_k, table_top_k = _search_sizes(query_type, retrieval_k)
        section = infer_text_section(query) if query_type in {"text", "mixed"} else None

        text_records = self.text_index.search(
            query,
            ticker=ticker,
            fiscal_year=fiscal_year,
            section=section,
            top_k=text_top_k,
        )
        table_records = (
            self.table_retriever.search(
                query,
                ticker=ticker,
                fiscal_year=fiscal_year,
                top_k=table_top_k,
            )
            if table_top_k
            else []
        )

        evidence = [_text_evidence(record, text_weight) for record in text_records]
        evidence.extend(_table_evidence(record, table_weight) for record in table_records)
        evidence.sort(key=lambda item: (-item["score"], item["evidence_type"], item["id"] or ""))
        if rerank:
            return self.reranker.rerank(query, evidence, top_k=top_k)
        return evidence[:top_k]


def _preview_text(content: str, max_chars: int = 260) -> str:
    return content[:max_chars].replace("\n", " ")


def _preview_rows(rows: list[list[str]], max_rows: int = 6) -> list[list[str]]:
    preview: list[list[str]] = []
    for row in rows:
        cleaned = [str(cell).strip() for cell in row]
        if any(cleaned):
            preview.append(cleaned)
        if len(preview) >= max_rows:
            break
    return preview


def _result_summary(record: dict) -> dict:
    summary = {
        "evidence_type": record["evidence_type"],
        "score": round(record["score"], 4),
        "raw_score": round(record["raw_score"], 4),
        "id": record["id"],
        "ticker": record["ticker"],
        "fiscal_year": record["fiscal_year"],
    }
    if "retrieval_score" in record:
        summary["retrieval_score"] = round(float(record.get("retrieval_score", 0.0)), 4)
    if "rerank_score" in record:
        summary["rerank_score"] = round(float(record.get("rerank_score", 0.0)), 4)
    if "rerank_features" in record:
        summary["rerank_features"] = record.get("rerank_features", {})
    if record["evidence_type"] == "text":
        summary["section"] = record.get("section")
        summary["text_preview"] = _preview_text(record.get("content", ""))
    else:
        summary["table_index"] = record.get("table_index")
        summary["core_metrics"] = record.get("core_metrics", [])
        summary["rows_preview"] = _preview_rows(record.get("rows", []))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid search over text and table evidence.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--text-chunks", default=DEFAULT_TEXT_CHUNKS_PATH, help="Path to text_chunks.jsonl.")
    parser.add_argument("--tables", default=DEFAULT_TABLE_CHUNKS_PATH, help="Path to table_chunks.jsonl.")
    parser.add_argument("--ticker", default=None, help="Optional ticker filter, e.g. AAPL.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year filter.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of evidence records to print.")
    parser.add_argument("--rerank", action="store_true", help="Apply rule-based evidence reranking.")
    parser.add_argument("--candidate-k", type=int, default=None, help="Number of initial candidates before reranking.")
    args = parser.parse_args()

    retriever = HybridRetriever.from_jsonl(args.text_chunks, args.tables)
    results = retriever.retrieve(
        args.query,
        ticker=args.ticker,
        fiscal_year=args.year,
        top_k=args.top_k,
        rerank=args.rerank,
        candidate_k=args.candidate_k,
    )
    for result in results:
        print(json.dumps(_result_summary(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
