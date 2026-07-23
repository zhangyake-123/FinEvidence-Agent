"""Shared text utilities for parsers and ingestion."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


class _TextExtractor(HTMLParser):
    """Small stdlib HTML-to-text fallback when BeautifulSoup is unavailable."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag in {"br", "p", "div", "tr", "li", "table", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "tr", "li", "table", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def read_text(path: str | Path) -> str:
    """Read a text file with a forgiving encoding strategy."""

    return Path(path).read_text(encoding="utf-8", errors="ignore")


def clean_text(text: str) -> str:
    """Normalize whitespace while keeping paragraph boundaries."""

    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def html_to_text(html: str) -> str:
    """Convert HTML to readable text."""

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        parser = _TextExtractor()
        parser.feed(html)
        return clean_text(parser.text())

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return clean_text(soup.get_text("\n"))


def chunk_text(text: str, max_chars: int = 4000, overlap_chars: int = 400) -> list[str]:
    """Split text into overlapping chunks using paragraph boundaries when possible."""

    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        paragraph_len = len(paragraph)
        if current and current_len + paragraph_len + 2 > max_chars:
            chunk = "\n\n".join(current).strip()
            chunks.append(chunk)
            overlap = chunk[-overlap_chars:] if overlap_chars > 0 else ""
            current = [overlap, paragraph] if overlap else [paragraph]
            current_len = sum(len(part) for part in current) + 2 * (len(current) - 1)
        else:
            current.append(paragraph)
            current_len += paragraph_len + 2

    if current:
        chunks.append("\n\n".join(current).strip())

    return [chunk for chunk in chunks if chunk]


def write_jsonl(records: Iterable[dict], path: str | Path) -> None:
    """Write records as UTF-8 JSON Lines."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
