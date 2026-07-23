"""HTML parser for generic ingestion."""

from __future__ import annotations

from pathlib import Path

from finevidence.data.schema import ParsedDocument, ParsedPage
from finevidence.data.text_utils import html_to_text


class HTMLDocumentParser:
    """Parse HTML into one normalized text document."""

    source_format = "html"

    def parse(self, path: str | Path, metadata: dict | None = None) -> list[ParsedDocument]:
        html = Path(path).read_text(encoding="utf-8", errors="ignore")
        text = html_to_text(html)
        pages = [ParsedPage(text=text)]
        return [ParsedDocument.from_path(path, self.source_format, pages, metadata)]
