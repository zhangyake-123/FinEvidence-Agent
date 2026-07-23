"""Parser interfaces for generic document ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from finevidence.data.schema import ParsedDocument


class IngestionError(RuntimeError):
    """Raised when a file cannot be parsed by the selected ingestion parser."""


class DocumentParser(Protocol):
    def parse(self, path: str | Path, metadata: dict | None = None) -> list[ParsedDocument]:
        """Parse one file into normalized documents."""
