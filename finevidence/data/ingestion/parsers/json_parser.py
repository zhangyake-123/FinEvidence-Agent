"""JSON parser for generic ingestion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from finevidence.data.filing_parser import clean_text
from finevidence.data.schema import ParsedDocument, ParsedPage


DEFAULT_TEXT_FIELDS = (
    "text",
    "content",
    "body",
    "evidence_text_full_page",
    "evidence_text",
    "justification",
    "answer",
    "question",
)

METADATA_FIELDS = (
    "source_dataset",
    "company",
    "ticker",
    "fiscal_year",
    "filing_type",
    "source_url",
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(_as_text(item) for item in value if _as_text(item))
    if isinstance(value, dict):
        return _record_text(value)
    return str(value)


def _selected_fields_text(record: dict, fields: list[str]) -> str:
    parts = [_as_text(record.get(field)) for field in fields if field in record]
    return "\n".join(part for part in parts if part.strip())


def _record_text(record: dict, text_fields: list[str] | None = None) -> str:
    fields = text_fields or []
    if fields:
        text = _selected_fields_text(record, fields)
        if text:
            return text

    text = _selected_fields_text(record, list(DEFAULT_TEXT_FIELDS))
    evidence = record.get("evidence")
    if isinstance(evidence, list):
        evidence_text = "\n".join(_as_text(item) for item in evidence if _as_text(item))
        text = "\n".join(part for part in (text, evidence_text) if part.strip())
    return text or json.dumps(record, ensure_ascii=False, sort_keys=True)


def _metadata_from_record(record: dict, base_metadata: dict) -> dict:
    metadata = dict(base_metadata)
    for field in METADATA_FIELDS:
        if record.get(field) is not None:
            metadata[field] = record[field]
    if record.get("doc_name"):
        metadata.setdefault("title", record["doc_name"])
        metadata.setdefault("doc_id", record["doc_name"])
    if record.get("id"):
        metadata.setdefault("doc_id", record["id"])
    if record.get("financebench_id"):
        metadata.setdefault("doc_id", record["financebench_id"])
    return metadata


def document_from_json_record(
    record: Any,
    path: str | Path,
    base_metadata: dict | None = None,
    record_index: int | None = None,
) -> ParsedDocument:
    """Convert one JSON value into a normalized document."""

    metadata = dict(base_metadata or {})
    if isinstance(record, dict):
        metadata = _metadata_from_record(record, metadata)
        text = _record_text(record, metadata.get("text_fields"))
    else:
        text = _as_text(record)

    if record_index is not None and not metadata.get("doc_id"):
        metadata["doc_id"] = f"{Path(path).stem}_{record_index:04d}"

    page = ParsedPage(text=clean_text(text))
    return ParsedDocument.from_path(
        path,
        "json",
        [page],
        metadata,
        doc_id=metadata.get("doc_id"),
        title=metadata.get("title"),
    )


class JSONDocumentParser:
    """Parse JSON objects or arrays into normalized documents."""

    source_format = "json"

    def parse(self, path: str | Path, metadata: dict | None = None) -> list[ParsedDocument]:
        with Path(path).open("r", encoding="utf-8") as file:
            data = json.load(file)

        records = data if isinstance(data, list) else [data]
        documents = [
            document_from_json_record(record, path, metadata, index)
            for index, record in enumerate(records, start=1)
        ]
        for document in documents:
            document.source_format = self.source_format
        return documents
