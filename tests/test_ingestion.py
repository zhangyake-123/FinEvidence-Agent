import json
import tempfile
import unittest
from pathlib import Path

from finevidence.data.ingestion.detector import detect_file_type, is_supported_file
from finevidence.data.ingestion.ingestor import ingest_path


def load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


class IngestionTest(unittest.TestCase):
    def test_detect_file_type(self) -> None:
        self.assertEqual(detect_file_type("report.html"), "html")
        self.assertEqual(detect_file_type("report.pdf"), "pdf")
        self.assertEqual(detect_file_type("records.jsonl"), "jsonl")
        self.assertEqual(detect_file_type("notes.md"), "text")
        self.assertFalse(is_supported_file("not_a_real_file.txt"))

    def test_ingest_directory_writes_text_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "input"
            input_dir.mkdir()
            output_path = root / "chunks.jsonl"

            (input_dir / "note.txt").write_text(
                "Revenue increased in 2025.\n\nGross margin improved.",
                encoding="utf-8",
            )
            (input_dir / "filing.html").write_text(
                "<html><body><h1>Item 1A. Risk Factors</h1><p>Supply chain risk remains material.</p></body></html>",
                encoding="utf-8",
            )
            (input_dir / "qa.jsonl").write_text(
                json.dumps(
                    {
                        "id": "qa_001",
                        "company": "Example Co",
                        "question": "What was revenue?",
                        "answer": "Revenue was 100.",
                        "evidence": [{"evidence_text": "Revenue was 100 in the filing."}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = ingest_path(
                input_path=input_dir,
                output_path=output_path,
                source_dataset="unit",
                metadata={"ticker": "TEST", "fiscal_year": 2025},
                max_chars=120,
                overlap_chars=0,
            )
            chunks = load_jsonl(output_path)

        self.assertEqual(result["files_seen"], 3)
        self.assertEqual(result["files_parsed"], 3)
        self.assertEqual(result["documents"], 3)
        self.assertGreaterEqual(result["text_chunks"], 3)
        self.assertEqual(len(chunks), result["written_chunks"])
        self.assertTrue(all(chunk["source_dataset"] == "unit" for chunk in chunks))
        self.assertTrue(all(chunk["ticker"] == "TEST" for chunk in chunks))
        self.assertTrue(any("Supply chain risk" in chunk["text"] for chunk in chunks))
        self.assertTrue(any("Revenue was 100" in chunk["text"] for chunk in chunks))
        self.assertEqual(len({chunk["chunk_id"] for chunk in chunks}), len(chunks))

    def test_jsonl_text_field_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "records.jsonl"
            output_path = root / "chunks.jsonl"
            input_path.write_text(
                json.dumps({"id": "custom_001", "ignored": "skip me", "body": "Keep this field."}) + "\n",
                encoding="utf-8",
            )

            ingest_path(
                input_path=input_path,
                output_path=output_path,
                source_dataset="custom",
                metadata={"text_fields": ["body"]},
                max_chars=100,
                overlap_chars=0,
            )
            chunks = load_jsonl(output_path)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["doc_id"], "custom_001")
        self.assertEqual(chunks[0]["text"], "Keep this field.")


if __name__ == "__main__":
    unittest.main()
