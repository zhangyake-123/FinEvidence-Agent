"""Shared data structures for document ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedPage:
    """One text-bearing page or logical section in a parsed document."""

    text: str
    page_number: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Normalized document produced by format-specific parsers."""

    doc_id: str
    source_path: str
    source_format: str
    pages: list[ParsedPage]
    source_dataset: str | None = None
    title: str | None = None
    company: str | None = None
    ticker: str | None = None
    fiscal_year: int | None = None
    filing_type: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        source_format: str,
        pages: list[ParsedPage],
        metadata: dict[str, Any] | None = None,
        doc_id: str | None = None,
        title: str | None = None,
    ) -> "ParsedDocument":
        """Build a normalized document from a file path and shared metadata."""

        path_obj = Path(path)
        values = metadata or {}
        return cls(
            doc_id=str(doc_id or values.get("doc_id") or path_obj.stem),
            source_path=path_obj.as_posix(),
            source_format=source_format,
            source_dataset=values.get("source_dataset"),
            title=title or values.get("title") or path_obj.stem,
            company=values.get("company"),
            ticker=values.get("ticker"),
            fiscal_year=values.get("fiscal_year"),
            filing_type=values.get("filing_type"),
            source_url=values.get("source_url"),
            pages=pages,
            metadata=dict(values),
        )
