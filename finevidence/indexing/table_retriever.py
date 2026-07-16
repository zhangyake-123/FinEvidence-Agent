"""Table-aware retrieval over processed SEC filing tables."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from finevidence.indexing.bm25_index import load_jsonl, tokenize


DEFAULT_TABLE_CHUNKS_PATH = Path("data/processed/table_chunks.jsonl")

FINANCIAL_QUERY_TERMS = {
    "income",
    "statement",
    "operations",
    "revenue",
    "sales",
    "gross",
    "margin",
    "profit",
    "operating",
    "net",
    "assets",
    "liabilities",
    "cash",
    "flow",
}


def _matches_metadata(
    record: dict,
    ticker: str | None = None,
    fiscal_year: int | None = None,
) -> bool:
    if ticker and record.get("ticker", "").upper() != ticker.upper():
        return False
    if fiscal_year is not None and int(record.get("fiscal_year", -1)) != fiscal_year:
        return False
    return True


def _cell_text(value: object) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text).strip()


def table_to_text(record: dict) -> str:
    """Flatten a table record into searchable text."""

    parts: list[str] = []
    parts.extend(_cell_text(column) for column in record.get("columns", []))
    for row in record.get("rows", []):
        parts.extend(_cell_text(cell) for cell in row)
    return " ".join(part for part in parts if part)


def _row_label(row: list[str]) -> str:
    labels: list[str] = []
    for cell in row[:3]:
        text = _cell_text(cell)
        if not text:
            continue
        if re.fullmatch(r"[$()0-9,.\- ]+", text):
            continue
        if text not in labels:
            labels.append(text)
    return " ".join(labels).lower()


def _is_noise_label(label: str) -> bool:
    return any(
        token in label
        for token in (
            "growth",
            "percentage",
            "percent",
            "remaining performance",
            "allocated",
            "definition",
            "per share",
            "earnings per share",
        )
    )


def core_financial_metrics(record: dict) -> set[str]:
    """Detect core financial statement rows in a table."""

    metrics: set[str] = set()
    for row in record.get("rows", []):
        label = _row_label(row)
        if not label or _is_noise_label(label):
            continue

        if re.search(r"\b(total )?(revenue|net sales|total net sales)\b", label):
            metrics.add("revenue")
        if re.search(r"\b(gross margin|gross profit)\b", label):
            metrics.add("gross_profit")
        if re.search(r"\boperating income\b", label):
            metrics.add("operating_income")
        if re.search(r"\bnet income\b", label):
            metrics.add("net_income")
        if re.search(r"\b(cost of revenue|cost of sales)\b", label):
            metrics.add("cost")
        if re.search(r"\b(total assets)\b", label):
            metrics.add("total_assets")
        if re.search(r"\b(total liabilities)\b", label):
            metrics.add("total_liabilities")
        if re.search(r"\b(cash and cash equivalents|cash equivalents)\b", label):
            metrics.add("cash")
        if re.search(r"\b(net cash|cash provided by|cash used in)\b", label):
            metrics.add("cash_flow")

    return metrics


def _table_signal_score(query: str, record: dict) -> float:
    query_terms = set(tokenize(query))
    query_lower = query.lower()
    core_metrics = core_financial_metrics(record)
    score = 0.0

    if query_terms & FINANCIAL_QUERY_TERMS:
        score += 1.5 * len(core_metrics)

    if (
        "income statement" in query_lower
        or "statement of income" in query_lower
        or "statements of income" in query_lower
        or "statement of operations" in query_lower
        or "statements of operations" in query_lower
    ):
        statement_metrics = {"revenue", "gross_profit", "operating_income", "net_income"}
        score += 3.0 * len(core_metrics & statement_metrics)
        if len(core_metrics & statement_metrics) >= 3:
            score += 4.0

    metric_query_map = {
        "revenue": {"revenue"},
        "sales": {"revenue"},
        "gross": {"gross_profit"},
        "margin": {"gross_profit"},
        "operating": {"operating_income"},
        "income": {"operating_income", "net_income"},
        "assets": {"total_assets"},
        "liabilities": {"total_liabilities"},
        "cash": {"cash", "cash_flow"},
        "flow": {"cash_flow"},
    }
    for term, metrics in metric_query_map.items():
        if term in query_terms:
            score += 2.0 * len(core_metrics & metrics)

    return score


class TableRetriever:
    """Keyword and table-structure retrieval for table_chunks.jsonl."""

    def __init__(self, records: Iterable[dict], k1: float = 1.5, b: float = 0.75) -> None:
        self.records = list(records)
        self.k1 = k1
        self.b = b
        self.documents = [table_to_text(record) for record in self.records]
        self.doc_tokens = [tokenize(document) for document in self.documents]
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_length = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0.0
        )
        self.term_frequencies = [Counter(tokens) for tokens in self.doc_tokens]
        self.document_frequencies = self._build_document_frequencies()
        self.idf = self._build_idf()

    @classmethod
    def from_jsonl(cls, path: str | Path = DEFAULT_TABLE_CHUNKS_PATH) -> "TableRetriever":
        return cls(load_jsonl(path))

    def search(
        self,
        query: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Search table records with metadata filters."""

        query_terms = tokenize(query)
        scored: list[tuple[float, float, float, int]] = []

        for index, record in enumerate(self.records):
            if not _matches_metadata(record, ticker, fiscal_year):
                continue
            bm25_score = self._score_document(query_terms, index) if query_terms else 0.0
            signal_score = _table_signal_score(query, record)
            score = bm25_score + signal_score
            scored.append((score, bm25_score, signal_score, index))

        scored.sort(key=lambda item: (-item[0], item[3]))
        results: list[dict] = []
        for score, bm25_score, signal_score, index in scored[:top_k]:
            record = dict(self.records[index])
            record["score"] = score
            record["bm25_score"] = bm25_score
            record["signal_score"] = signal_score
            record["core_metrics"] = sorted(core_financial_metrics(record))
            results.append(record)
        return results

    def _build_document_frequencies(self) -> Counter:
        frequencies: Counter = Counter()
        for tokens in self.doc_tokens:
            frequencies.update(set(tokens))
        return frequencies

    def _build_idf(self) -> dict[str, float]:
        doc_count = len(self.records)
        return {
            term: math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            for term, df in self.document_frequencies.items()
        }

    def _score_document(self, query_terms: list[str], document_index: int) -> float:
        if not query_terms or not self.avg_doc_length:
            return 0.0

        score = 0.0
        term_frequency = self.term_frequencies[document_index]
        doc_length = self.doc_lengths[document_index]

        for term in query_terms:
            frequency = term_frequency.get(term, 0)
            if frequency == 0:
                continue

            numerator = frequency * (self.k1 + 1)
            denominator = frequency + self.k1 * (
                1 - self.b + self.b * doc_length / self.avg_doc_length
            )
            score += self.idf.get(term, 0.0) * numerator / denominator

        return score


def _preview_rows(record: dict, max_rows: int = 8) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in record.get("rows", []):
        cleaned = [_cell_text(cell) for cell in row]
        if any(cleaned):
            rows.append(cleaned)
        if len(rows) >= max_rows:
            break
    return rows


def _result_summary(record: dict) -> dict:
    return {
        "score": round(record.get("score", 0.0), 4),
        "bm25_score": round(record.get("bm25_score", 0.0), 4),
        "signal_score": round(record.get("signal_score", 0.0), 4),
        "table_id": record.get("table_id"),
        "ticker": record.get("ticker"),
        "fiscal_year": record.get("fiscal_year"),
        "table_index": record.get("table_index"),
        "core_metrics": record.get("core_metrics", []),
        "rows_preview": _preview_rows(record),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Search processed filing table chunks.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--tables", default=DEFAULT_TABLE_CHUNKS_PATH, help="Path to table_chunks.jsonl.")
    parser.add_argument("--ticker", default=None, help="Optional ticker filter, e.g. MSFT.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year filter.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to print.")
    args = parser.parse_args()

    retriever = TableRetriever.from_jsonl(args.tables)
    results = retriever.search(
        args.query,
        ticker=args.ticker,
        fiscal_year=args.year,
        top_k=args.top_k,
    )
    for result in results:
        print(json.dumps(_result_summary(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
