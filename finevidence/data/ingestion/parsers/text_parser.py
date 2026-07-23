"""Plain text and Markdown parser."""

from __future__ import annotations

from pathlib import Path

from finevidence.data.schema import ParsedDocument, ParsedPage
from finevidence.data.text_utils import clean_text


class TextDocumentParser:
    """Parse a text-like file into one normalized document."""

    source_format = "text"

    def parse(self, path: str | Path, metadata: dict | None = None) -> list[ParsedDocument]:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        page = ParsedPage(text=clean_text(text))
        return [ParsedDocument.from_path(path, self.source_format, [page], metadata)]
