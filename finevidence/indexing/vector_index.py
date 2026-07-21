"""Lightweight vector retrieval over processed filing text chunks."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable

from finevidence.indexing.bm25_index import DEFAULT_TEXT_CHUNKS_PATH, load_jsonl, tokenize


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


def _normalize(vector: dict[str, float]) -> dict[str, float]:
    length = math.sqrt(sum(value * value for value in vector.values()))
    if not length:
        return vector
    return {term: value / length for term, value in vector.items()}


def _dot(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(term, 0.0) for term, value in left.items())


class VectorIndex:
    """A dependency-free TF-IDF cosine index for text_chunks.jsonl records."""

    def __init__(self, records: Iterable[dict]) -> None:
        self.records = list(records)
        self.documents = [self._document_text(record) for record in self.records]
        self.doc_tokens = [tokenize(document) for document in self.documents]
        self.document_frequencies = self._build_document_frequencies()
        self.idf = self._build_idf()
        self.vectors = [self._build_vector(tokens) for tokens in self.doc_tokens]

    @classmethod
    def from_jsonl(cls, path: str | Path = DEFAULT_TEXT_CHUNKS_PATH) -> "VectorIndex":
        return cls(load_jsonl(path))

    def search(
        self,
        query: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        section: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Search chunks by TF-IDF cosine similarity with optional metadata filters."""

        query_vector = self._build_vector(tokenize(query))
        scored: list[tuple[float, int]] = []

        for index, record in enumerate(self.records):
            if not _matches_metadata(record, ticker, fiscal_year, section):
                continue
            score = _dot(query_vector, self.vectors[index]) if query_vector else 0.0
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
            term: math.log((1 + doc_count) / (1 + document_frequency)) + 1.0
            for term, document_frequency in self.document_frequencies.items()
        }

    def _build_vector(self, tokens: list[str]) -> dict[str, float]:
        frequencies = Counter(tokens)
        vector = {
            term: (1.0 + math.log(frequency)) * self.idf.get(term, 0.0)
            for term, frequency in frequencies.items()
            if term in self.idf
        }
        return _normalize(vector)


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
    parser = argparse.ArgumentParser(description="Search processed filing text chunks with TF-IDF vectors.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--chunks", default=DEFAULT_TEXT_CHUNKS_PATH, help="Path to text_chunks.jsonl.")
    parser.add_argument("--ticker", default=None, help="Optional ticker filter, e.g. AAPL.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year filter.")
    parser.add_argument("--section", default=None, help="Optional section substring filter.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to print.")
    args = parser.parse_args()

    index = VectorIndex.from_jsonl(args.chunks)
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
