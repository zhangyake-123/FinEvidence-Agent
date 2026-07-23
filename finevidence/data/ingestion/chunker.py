"""Convert normalized documents into FinEvidence text chunk records."""

from __future__ import annotations

import re

from finevidence.data.schema import ParsedDocument, ParsedPage
from finevidence.data.text_utils import chunk_text, clean_text


def _slug(text: object) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")
    return value[:80] or "document"


def _chunk_id(document: ParsedDocument, page: ParsedPage, chunk_index: int) -> str:
    page_part = f"p{page.page_number:04d}" if page.page_number is not None else "full"
    return f"{_slug(document.source_dataset or 'local')}_{_slug(document.doc_id)}_{page_part}_{chunk_index:04d}"


def chunk_document(
    document: ParsedDocument,
    max_chars: int = 4000,
    overlap_chars: int = 400,
) -> list[dict]:
    """Chunk one parsed document into records compatible with text_chunks.jsonl."""

    records: list[dict] = []
    for page in document.pages:
        text = clean_text(page.text)
        if not text:
            continue
        for chunk_index, chunk in enumerate(chunk_text(text, max_chars, overlap_chars), start=1):
            records.append(
                {
                    "chunk_id": _chunk_id(document, page, chunk_index),
                    "source_dataset": document.source_dataset,
                    "source_format": document.source_format,
                    "doc_id": document.doc_id,
                    "title": document.title,
                    "company": document.company,
                    "ticker": document.ticker,
                    "fiscal_year": document.fiscal_year,
                    "filing_type": document.filing_type,
                    "section": page.section,
                    "page": page.page_number,
                    "text": chunk,
                    "source_path": document.source_path,
                    "source_url": document.source_url,
                }
            )
    return records
