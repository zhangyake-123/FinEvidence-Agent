"""BM25 retrieval over processed filing text chunks."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Iterable


DEFAULT_TEXT_CHUNKS_PATH = Path("data/processed/text_chunks.jsonl")


def load_jsonl(path: str | Path) -> list[dict]:
    """Load JSONL records from disk."""

    records: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def tokenize(text: str) -> list[str]:
    """Tokenize text for simple financial-document keyword retrieval."""

    return re.findall(r"[a-z0-9]+", text.lower())


def _matches_metadata(
    record: dict,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    section: str | None = None,
) -> bool:
    if ticker and record.get("ticker", "").upper() != ticker.upper():
        return False
    if fiscal_year is not None and int(record.get("fiscal_year", -1)) != fiscal_year:
        return False
    if section:
        record_section = record.get("section", "").lower()
        if section.lower() not in record_section:
            return False
    return True


class BM25Index:
    """A small BM25 index for text_chunks.jsonl records."""

    def __init__(self, records: Iterable[dict], k1: float = 1.5, b: float = 0.75) -> None:
        self.records = list(records)
        self.k1 = k1
        self.b = b
        self.documents = [self._document_text(record) for record in self.records]
        self.doc_tokens = [tokenize(document) for document in self.documents]
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_length = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0.0
        )
        self.term_frequencies = [Counter(tokens) for tokens in self.doc_tokens]
        self.document_frequencies = self._build_document_frequencies()
        self.idf = self._build_idf()

    @classmethod
    def from_jsonl(cls, path: str | Path = DEFAULT_TEXT_CHUNKS_PATH) -> "BM25Index":
        return cls(load_jsonl(path))

    def search(
        self,
        query: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        section: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Search chunks by query with optional metadata filters."""

        query_terms = tokenize(query)
        scored: list[tuple[float, int]] = []

        for index, record in enumerate(self.records):
            if not _matches_metadata(record, ticker, fiscal_year, section):
                continue
            score = self._score_document(query_terms, index) if query_terms else 0.0
            scored.append((score, index))

        scored.sort(key=lambda item: (-item[0], item[1]))
        results: list[dict] = []
        for score, index in scored[:top_k]:
            record = dict(self.records[index])
            record["score"] = score
            results.append(record)
        return results

    def _document_text(self, record: dict) -> str:
        return " ".join(
            [
                str(record.get("section", "")),
                str(record.get("text", "")),
            ]
        )

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


def _result_summary(record: dict, max_chars: int = 300) -> dict:
    text = record.get("text", "")
    return {
        "score": round(record.get("score", 0.0), 4),
        "chunk_id": record.get("chunk_id"),
        "ticker": record.get("ticker"),
        "fiscal_year": record.get("fiscal_year"),
        "section": record.get("section"),
        "text_preview": text[:max_chars].replace("\n", " "),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Search processed filing text chunks with BM25.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--chunks", default=DEFAULT_TEXT_CHUNKS_PATH, help="Path to text_chunks.jsonl.")
    parser.add_argument("--ticker", default=None, help="Optional ticker filter, e.g. AAPL.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year filter.")
    parser.add_argument("--section", default=None, help="Optional section substring filter.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to print.")
    args = parser.parse_args()

    index = BM25Index.from_jsonl(args.chunks)
    results = index.search(
        args.query,
        ticker=args.ticker,
        fiscal_year=args.year,
        section=args.section,
        top_k=args.top_k,
    )
    for result in results:
        print(json.dumps(_result_summary(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
