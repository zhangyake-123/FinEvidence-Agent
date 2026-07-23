"""Parse SEC 10-K HTML filings into filing metadata and text chunks."""

from __future__ import annotations

import re
from pathlib import Path

from finevidence.data.text_utils import chunk_text, clean_text, html_to_text, read_text, write_jsonl


RAW_FILINGS_ROOT = Path("data/raw/sec/filings")
PROCESSED_ROOT = Path("data/processed")

SECTION_KEYS = {
    "1": "Item 1. Business",
    "1a": "Item 1A. Risk Factors",
    "1b": "Item 1B. Unresolved Staff Comments",
    "2": "Item 2. Properties",
    "3": "Item 3. Legal Proceedings",
    "4": "Item 4. Mine Safety Disclosures",
    "5": "Item 5. Market for Registrant's Common Equity",
    "6": "Item 6. Selected Financial Data",
    "7": "Item 7. Management's Discussion and Analysis",
    "7a": "Item 7A. Quantitative and Qualitative Disclosures",
    "8": "Item 8. Financial Statements and Supplementary Data",
    "9": "Item 9. Changes in and Disagreements with Accountants",
    "9a": "Item 9A. Controls and Procedures",
    "9b": "Item 9B. Other Information",
    "10": "Item 10. Directors, Executive Officers and Corporate Governance",
    "11": "Item 11. Executive Compensation",
    "12": "Item 12. Security Ownership",
    "13": "Item 13. Certain Relationships and Related Transactions",
    "14": "Item 14. Principal Accountant Fees and Services",
    "15": "Item 15. Exhibits and Financial Statement Schedules",
}


def infer_ticker_and_year(path: str | Path) -> tuple[str, int]:
    """Infer ticker and fiscal year from data/raw/sec/filings/{TICKER}/{YEAR}."""

    parts = Path(path).parts
    for index, part in enumerate(parts):
        if part == "filings" and index + 2 < len(parts):
            return parts[index + 1], int(parts[index + 2])
    raise ValueError(f"Cannot infer ticker/year from path: {path}")


def iter_filing_paths(root: str | Path = RAW_FILINGS_ROOT) -> list[Path]:
    """Return downloaded 10-K HTML files under the raw filings root."""

    root_path = Path(root)
    suffixes = {".html", ".htm"}
    return sorted(
        path
        for path in root_path.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    )


def make_filing_record(path: str | Path) -> dict:
    """Build one metadata record for a raw SEC filing."""

    ticker, fiscal_year = infer_ticker_and_year(path)
    source_path = Path(path)
    return {
        "ticker": ticker,
        "company": None,
        "fiscal_year": fiscal_year,
        "filing_type": "10-K",
        "source_path": source_path.as_posix(),
    }


def split_sections(text: str) -> dict[str, str]:
    """Split filing text by common Form 10-K Item headings."""

    lines = text.splitlines()
    headings: list[tuple[int, str]] = []
    item_pattern = re.compile(r"^\s*item\s+([0-9]+[a-c]?)\s*[\.\-:)]?\s*(.*)$", re.I)

    for line_index, line in enumerate(lines):
        compact = line.strip()
        if len(compact) > 180:
            continue
        match = item_pattern.match(compact)
        if not match:
            continue
        key = match.group(1).lower()
        if key in SECTION_KEYS:
            headings.append((line_index, key))

    if not headings:
        return {"Full Text": text}

    sections: dict[str, str] = {}
    for heading_index, (start_line, key) in enumerate(headings):
        end_line = headings[heading_index + 1][0] if heading_index + 1 < len(headings) else len(lines)
        body = clean_text("\n".join(lines[start_line:end_line]))
        if len(body) < 200:
            continue
        section_name = SECTION_KEYS[key]
        if section_name not in sections or len(body) > len(sections[section_name]):
            sections[section_name] = body

    return sections or {"Full Text": text}


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return value[:60] or "section"


def parse_filing_file(path: str | Path, max_chars: int = 4000, overlap_chars: int = 400) -> tuple[dict, list[dict]]:
    """Parse one SEC HTML filing into metadata and text chunk records."""

    filing = make_filing_record(path)
    text = html_to_text(read_text(path))
    sections = split_sections(text)
    chunks: list[dict] = []

    for section_name, section_text in sections.items():
        section_slug = _slug(section_name)
        for chunk_index, chunk in enumerate(chunk_text(section_text, max_chars, overlap_chars), start=1):
            chunk_id = (
                f"{filing['ticker']}_{filing['fiscal_year']}_10K_"
                f"{section_slug}_{chunk_index:04d}"
            )
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "ticker": filing["ticker"],
                    "fiscal_year": filing["fiscal_year"],
                    "filing_type": filing["filing_type"],
                    "section": section_name,
                    "text": chunk,
                    "source_path": filing["source_path"],
                }
            )

    return filing, chunks


def parse_filings(
    raw_root: str | Path = RAW_FILINGS_ROOT,
    processed_root: str | Path = PROCESSED_ROOT,
    max_chars: int = 4000,
    overlap_chars: int = 400,
) -> tuple[list[dict], list[dict]]:
    """Parse all downloaded SEC filings and write filing index plus text chunks."""

    filings: list[dict] = []
    chunks: list[dict] = []

    for path in iter_filing_paths(raw_root):
        filing, filing_chunks = parse_filing_file(path, max_chars, overlap_chars)
        filings.append(filing)
        chunks.extend(filing_chunks)

    processed_path = Path(processed_root)
    write_jsonl(filings, processed_path / "filings_index.jsonl")
    write_jsonl(chunks, processed_path / "text_chunks.jsonl")
    return filings, chunks


def main() -> None:
    filings, chunks = parse_filings()
    print(f"parsed_filings={len(filings)} text_chunks={len(chunks)}")


if __name__ == "__main__":
    main()
