"""HTML parser for generic ingestion."""

from __future__ import annotations

from pathlib import Path

from finevidence.data.filing_parser import html_to_text, split_sections
from finevidence.data.schema import ParsedDocument, ParsedPage


class HTMLDocumentParser:
    """Parse HTML into section-aware text pages."""

    source_format = "html"

    def parse(self, path: str | Path, metadata: dict | None = None) -> list[ParsedDocument]:
        html = Path(path).read_text(encoding="utf-8", errors="ignore")
        text = html_to_text(html)
        sections = split_sections(text)
        pages = [
            ParsedPage(text=section_text, section=section_name)
            for section_name, section_text in sections.items()
        ]
        return [ParsedDocument.from_path(path, self.source_format, pages, metadata)]
