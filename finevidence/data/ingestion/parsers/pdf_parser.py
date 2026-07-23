"""PDF parser for generic ingestion."""

from __future__ import annotations

from pathlib import Path

from finevidence.data.filing_parser import clean_text
from finevidence.data.ingestion.parsers.base import IngestionError
from finevidence.data.schema import ParsedDocument, ParsedPage


def _load_pdf_reader():
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise IngestionError(
            "PDF ingestion requires pypdf. Install it with: python3 -m pip install pypdf"
        ) from exc
    return PdfReader


class PDFDocumentParser:
    """Parse PDF text one physical page at a time."""

    source_format = "pdf"

    def parse(self, path: str | Path, metadata: dict | None = None) -> list[ParsedDocument]:
        PdfReader = _load_pdf_reader()
        reader = PdfReader(str(path))
        pages: list[ParsedPage] = []
        for page_index, page in enumerate(reader.pages, start=1):
            text = clean_text(page.extract_text() or "")
            if text:
                pages.append(ParsedPage(text=text, page_number=page_index))
        return [ParsedDocument.from_path(path, self.source_format, pages, metadata)]
