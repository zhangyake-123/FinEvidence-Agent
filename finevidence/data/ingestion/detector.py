"""File type detection for generic ingestion."""

from __future__ import annotations

from pathlib import Path


SUFFIX_TO_TYPE = {
    ".htm": "html",
    ".html": "html",
    ".pdf": "pdf",
    ".txt": "text",
    ".md": "text",
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
}


def detect_file_type(path: str | Path) -> str:
    """Detect a supported ingestion file type from the file extension."""

    suffix = Path(path).suffix.lower()
    file_type = SUFFIX_TO_TYPE.get(suffix)
    if file_type is None:
        raise ValueError(f"Unsupported file type for ingestion: {path}")
    return file_type


def is_supported_file(path: str | Path) -> bool:
    return Path(path).is_file() and Path(path).suffix.lower() in SUFFIX_TO_TYPE
