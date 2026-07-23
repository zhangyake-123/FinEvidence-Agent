"""JSON Lines parser for generic ingestion."""

from __future__ import annotations

import json
from pathlib import Path

from finevidence.data.ingestion.parsers.json_parser import document_from_json_record


class JSONLDocumentParser:
    """Parse each JSONL line into one normalized document."""

    source_format = "jsonl"

    def parse(self, path: str | Path, metadata: dict | None = None) -> list:
        documents = []
        with Path(path).open("r", encoding="utf-8") as file:
            for index, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                document = document_from_json_record(
                    json.loads(stripped),
                    path,
                    metadata,
                    record_index=index,
                )
                document.source_format = self.source_format
                documents.append(document)
        return documents
