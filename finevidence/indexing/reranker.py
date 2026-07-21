"""Rule-based reranking for retrieved financial evidence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

from finevidence.indexing.bm25_index import DEFAULT_TEXT_CHUNKS_PATH, tokenize
from finevidence.indexing.table_retriever import DEFAULT_TABLE_CHUNKS_PATH


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "by",
    "did",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "over",
    "the",
    "to",
    "was",
    "were",
    "what",
}

RISK_TERMS = {"risk", "risks", "competition", "competitive", "supply", "chain", "regulatory", "legal"}
BUSINESS_TERMS = {"business", "products", "services", "customers", "strategy"}
MDA_TERMS = {"management", "discussion", "md", "mda", "operations", "results"}
TABLE_TERMS = {
    "assets",
    "cash",
    "debt",
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

METRIC_QUERY_TERMS = {
    "revenue": {"revenue", "revenues", "sales"},
    "gross_profit": {"gross", "profit"},
    "operating_income": {"operating"},
    "net_income": {"net", "income", "earnings"},
    "cash_flow": {"cash", "flow"},
    "total_assets": {"assets"},
    "total_liabilities": {"liabilities", "debt"},
    "cash": {"cash", "equivalents"},
}


def _query_terms(query: str) -> set[str]:
    return {term for term in tokenize(query) if term not in STOPWORDS}


def infer_query_type(query: str) -> str:
    """Infer whether a query is primarily text, table, or mixed."""

    terms = _query_terms(query)
    query_lower = query.lower()
    text_hits = len(terms & (RISK_TERMS | BUSINESS_TERMS | MDA_TERMS))
    table_hits = len(terms & TABLE_TERMS)

    if any(phrase in query_lower for phrase in ("risk factors", "supply chain", "legal proceedings")):
        text_hits += 3
    if any(phrase in query_lower for phrase in ("income statement", "balance sheet", "cash flow")):
        table_hits += 3

    if text_hits and table_hits:
        return "mixed"
    if table_hits:
        return "table"
    return "text"


def infer_requested_metrics(query: str) -> set[str]:
    """Infer table metrics that should receive a reranking boost."""

    terms = _query_terms(query)
    query_lower = query.lower()
    metrics: set[str] = set()

    if "gross margin" in query_lower:
        metrics.update({"revenue", "gross_profit"})
    if "net margin" in query_lower:
        metrics.update({"revenue", "net_income"})
    if "operating margin" in query_lower:
        metrics.update({"revenue", "operating_income"})
    if "free cash flow" in query_lower:
        metrics.add("cash_flow")
    if "income statement" in query_lower or "statement of operations" in query_lower:
        metrics.update({"revenue", "gross_profit", "operating_income", "net_income"})

    for metric, metric_terms in METRIC_QUERY_TERMS.items():
        if terms & metric_terms:
            metrics.add(metric)

    return metrics


def _as_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _cell_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _evidence_text(record: dict) -> str:
    parts: list[str] = []
    parts.append(str(record.get("section", "")))
    parts.append(str(record.get("content", "")))
    parts.append(str(record.get("text", "")))
    parts.append(str(record.get("text_preview", "")))
    parts.extend(str(metric) for metric in record.get("core_metrics", []))
    parts.extend(_cell_text(column) for column in record.get("columns", []))
    for row in record.get("rows", []):
        parts.extend(_cell_text(cell) for cell in row)
    return " ".join(part for part in parts if part)


def _score_range(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    return min(values), max(values)


def _normalized_score(score: float, minimum: float, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return score / maximum


def _keyword_overlap(query_terms: set[str], record: dict) -> float:
    if not query_terms:
        return 0.0
    evidence_terms = set(tokenize(_evidence_text(record)))
    if not evidence_terms:
        return 0.0
    overlap = query_terms & evidence_terms
    return len(overlap) / math.sqrt(len(query_terms) * len(evidence_terms))


def _section_bonus(query: str, record: dict) -> float:
    if record.get("evidence_type") != "text":
        return 0.0

    terms = _query_terms(query)
    section = str(record.get("section", "")).lower()
    bonus = 0.0

    if terms & RISK_TERMS:
        if "item 1a" in section or "risk factors" in section:
            bonus += 0.35
    if terms & BUSINESS_TERMS:
        if "item 1. business" in section or section.strip() == "item 1":
            bonus += 0.25
    if terms & MDA_TERMS:
        if "item 7" in section or "management" in section:
            bonus += 0.2

    return bonus


def _metric_bonus(query: str, record: dict) -> tuple[float, list[str], list[str]]:
    requested = sorted(infer_requested_metrics(query))
    if record.get("evidence_type") != "table" or not requested:
        return 0.0, requested, []

    core_metrics = {str(metric) for metric in record.get("core_metrics", [])}
    matched = sorted(core_metrics & set(requested))
    bonus = min(0.6, 0.18 * len(matched))
    statement_metrics = {"revenue", "gross_profit", "operating_income", "net_income"}

    if set(requested) & statement_metrics:
        statement_metric_count = len(core_metrics & statement_metrics)
        if statement_metric_count >= 3:
            bonus += 0.22
        if statement_metric_count >= 4:
            bonus += 0.18

        evidence_text = _evidence_text(record).lower()
        if "income statement" in evidence_text or "statement of operations" in evidence_text:
            bonus += 0.2

    return bonus, requested, matched


def _evidence_type_bonus(query_type: str, record: dict) -> float:
    evidence_type = record.get("evidence_type")
    if query_type == "table" and evidence_type == "table":
        return 0.12
    if query_type == "text" and evidence_type == "text":
        return 0.12
    if query_type == "mixed":
        return 0.06
    return 0.0


def _rerank_one(
    query: str,
    record: dict,
    original_score: float,
    normalized_score: float,
    query_type: str,
    query_terms: set[str],
) -> dict:
    keyword_score = _keyword_overlap(query_terms, record)
    section_bonus = _section_bonus(query, record)
    metric_bonus, requested_metrics, matched_metrics = _metric_bonus(query, record)
    evidence_type_bonus = _evidence_type_bonus(query_type, record)

    rerank_score = (
        0.55 * normalized_score
        + 0.3 * keyword_score
        + section_bonus
        + metric_bonus
        + evidence_type_bonus
    )

    reranked = dict(record)
    reranked["retrieval_score"] = original_score
    reranked["rerank_score"] = rerank_score
    reranked["score"] = rerank_score
    reranked["rerank_features"] = {
        "query_type": query_type,
        "normalized_retrieval_score": normalized_score,
        "keyword_overlap": keyword_score,
        "section_bonus": section_bonus,
        "metric_bonus": metric_bonus,
        "evidence_type_bonus": evidence_type_bonus,
        "requested_metrics": requested_metrics,
        "matched_metrics": matched_metrics,
    }
    return reranked


def rerank_evidence(query: str, evidence: Iterable[dict], top_k: int | None = None) -> list[dict]:
    """Return evidence candidates sorted by retrieval score plus financial relevance signals."""

    candidates = list(evidence)
    original_scores = [_as_float(record.get("score", record.get("raw_score", 0.0))) for record in candidates]
    minimum, maximum = _score_range(original_scores)
    query_type = infer_query_type(query)
    query_terms = _query_terms(query)

    reranked: list[dict] = []
    for index, record in enumerate(candidates):
        original_score = original_scores[index]
        normalized = _normalized_score(original_score, minimum, maximum)
        item = _rerank_one(query, record, original_score, normalized, query_type, query_terms)
        item["original_rank"] = index + 1
        reranked.append(item)

    reranked.sort(
        key=lambda item: (
            -item["rerank_score"],
            item["original_rank"],
            item.get("evidence_type", ""),
            item.get("id") or "",
        )
    )
    return reranked[:top_k] if top_k is not None else reranked


class EvidenceReranker:
    """Small wrapper class for reranking evidence candidates."""

    def rerank(self, query: str, evidence: Iterable[dict], top_k: int | None = None) -> list[dict]:
        return rerank_evidence(query, evidence, top_k=top_k)


def _preview_text(content: str, max_chars: int = 260) -> str:
    return content[:max_chars].replace("\n", " ")


def _preview_rows(rows: list[list[str]], max_rows: int = 5) -> list[list[str]]:
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
        "evidence_type": record.get("evidence_type"),
        "rerank_score": round(_as_float(record.get("rerank_score")), 4),
        "retrieval_score": round(_as_float(record.get("retrieval_score")), 4),
        "id": record.get("id"),
        "ticker": record.get("ticker"),
        "fiscal_year": record.get("fiscal_year"),
        "rerank_features": record.get("rerank_features", {}),
    }
    if record.get("evidence_type") == "table":
        summary["table_index"] = record.get("table_index")
        summary["core_metrics"] = record.get("core_metrics", [])
        summary["rows_preview"] = _preview_rows(record.get("rows", []))
    else:
        summary["section"] = record.get("section")
        summary["text_preview"] = _preview_text(str(record.get("content") or record.get("text") or ""))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Rerank hybrid FinEvidence retrieval candidates.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--text-chunks", default=DEFAULT_TEXT_CHUNKS_PATH, help="Path to text_chunks.jsonl.")
    parser.add_argument("--tables", default=DEFAULT_TABLE_CHUNKS_PATH, help="Path to table_chunks.jsonl.")
    parser.add_argument("--ticker", default=None, help="Optional ticker filter, e.g. AAPL.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year filter.")
    parser.add_argument("--candidate-k", type=int, default=20, help="Number of initial candidates to retrieve.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of reranked results to print.")
    args = parser.parse_args()

    from finevidence.indexing.hybrid_retriever import HybridRetriever

    retriever = HybridRetriever.from_jsonl(args.text_chunks, args.tables)
    candidates = retriever.retrieve(
        args.query,
        ticker=args.ticker,
        fiscal_year=args.year,
        top_k=args.candidate_k,
    )
    results = rerank_evidence(args.query, candidates, top_k=args.top_k)
    for result in results:
        print(json.dumps(_result_summary(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
