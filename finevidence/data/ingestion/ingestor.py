"""CLI and orchestration for generic document ingestion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from finevidence.data.ingestion.chunker import chunk_document
from finevidence.data.ingestion.detector import detect_file_type, is_supported_file
from finevidence.data.ingestion.parsers.base import DocumentParser
from finevidence.data.ingestion.parsers.html_parser import HTMLDocumentParser
from finevidence.data.ingestion.parsers.json_parser import JSONDocumentParser
from finevidence.data.ingestion.parsers.jsonl_parser import JSONLDocumentParser
from finevidence.data.ingestion.parsers.pdf_parser import PDFDocumentParser
from finevidence.data.ingestion.parsers.text_parser import TextDocumentParser
from finevidence.data.text_utils import write_jsonl


DEFAULT_INGESTION_OUTPUT = Path("data/processed/text_chunks.jsonl")

PARSERS: dict[str, DocumentParser] = {
    "html": HTMLDocumentParser(),
    "json": JSONDocumentParser(),
    "jsonl": JSONLDocumentParser(),
    "pdf": PDFDocumentParser(),
    "text": TextDocumentParser(),
}


def _load_jsonl(path: str | Path) -> list[dict]:
    records: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def iter_input_files(input_path: str | Path) -> list[Path]:
    """Return supported files from a file or directory path."""

    path = Path(input_path)
    if path.is_file():
        detect_file_type(path)
        return [path]
    if not path.exists():
        raise FileNotFoundError(f"Ingestion input does not exist: {input_path}")
    return sorted(file for file in path.rglob("*") if is_supported_file(file))


def ingest_path(
    input_path: str | Path,
    output_path: str | Path = DEFAULT_INGESTION_OUTPUT,
    source_dataset: str | None = None,
    metadata: dict | None = None,
    max_chars: int = 4000,
    overlap_chars: int = 400,
    append: bool = False,
    ignore_errors: bool = False,
) -> dict:
    """Parse supported files under input_path and write text chunk JSONL."""

    files = iter_input_files(input_path)
    base_metadata = dict(metadata or {})
    if source_dataset:
        base_metadata["source_dataset"] = source_dataset

    documents = []
    chunks: list[dict] = []
    errors: list[dict] = []
    parsed_files = 0

    for file_path in files:
        file_type = detect_file_type(file_path)
        parser = PARSERS[file_type]
        try:
            file_documents = parser.parse(file_path, base_metadata)
        except Exception as error:
            if not ignore_errors:
                raise
            errors.append({"path": file_path.as_posix(), "error": str(error)})
            continue
        parsed_files += 1
        documents.extend(file_documents)
        for document in file_documents:
            chunks.extend(chunk_document(document, max_chars=max_chars, overlap_chars=overlap_chars))

    output = Path(output_path)
    output_records = _load_jsonl(output) + chunks if append and output.exists() else chunks
    write_jsonl(output_records, output)

    return {
        "input": str(input_path),
        "output": str(output),
        "files_seen": len(files),
        "files_parsed": parsed_files,
        "documents": len(documents),
        "text_chunks": len(chunks),
        "written_chunks": len(output_records),
        "errors": errors,
    }


def _parse_metadata(values: list[str]) -> dict:
    metadata: dict[str, object] = {}
    for value in values:
        key, separator, raw = value.partition("=")
        if not separator or not key:
            raise ValueError(f"Metadata must use KEY=VALUE format: {value}")
        metadata[key] = raw
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest files into FinEvidence text chunks.")
    parser.add_argument("--input", required=True, help="Input file or directory.")
    parser.add_argument("--output", default=DEFAULT_INGESTION_OUTPUT, help="Output text_chunks JSONL path.")
    parser.add_argument("--source-dataset", default=None, help="Dataset label, e.g. sec or financebench.")
    parser.add_argument("--ticker", default=None, help="Optional ticker metadata.")
    parser.add_argument("--company", default=None, help="Optional company metadata.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year metadata.")
    parser.add_argument("--filing-type", default=None, help="Optional filing type metadata.")
    parser.add_argument("--title", default=None, help="Optional title metadata.")
    parser.add_argument("--doc-id", default=None, help="Optional document id metadata.")
    parser.add_argument("--source-url", default=None, help="Optional source URL metadata.")
    parser.add_argument("--text-field", action="append", default=[], help="JSON/JSONL text field to ingest.")
    parser.add_argument("--metadata", action="append", default=[], help="Extra metadata as KEY=VALUE.")
    parser.add_argument("--max-chars", type=int, default=4000, help="Maximum characters per chunk.")
    parser.add_argument("--overlap-chars", type=int, default=400, help="Chunk overlap in characters.")
    parser.add_argument("--append", action="store_true", help="Append to an existing output JSONL.")
    parser.add_argument("--ignore-errors", action="store_true", help="Continue after parse errors.")
    args = parser.parse_args()

    metadata = _parse_metadata(args.metadata)
    for key, value in {
        "ticker": args.ticker,
        "company": args.company,
        "fiscal_year": args.year,
        "filing_type": args.filing_type,
        "title": args.title,
        "doc_id": args.doc_id,
        "source_url": args.source_url,
    }.items():
        if value is not None:
            metadata[key] = value
    if args.text_field:
        metadata["text_fields"] = args.text_field

    result = ingest_path(
        input_path=args.input,
        output_path=args.output,
        source_dataset=args.source_dataset,
        metadata=metadata,
        max_chars=args.max_chars,
        overlap_chars=args.overlap_chars,
        append=args.append,
        ignore_errors=args.ignore_errors,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
