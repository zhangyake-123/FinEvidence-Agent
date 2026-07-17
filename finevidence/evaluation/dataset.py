
"""Dataset helpers for FinEvidence evaluation JSONL files."""

from __future__ import annotations

import json
from pathlib import Path


REQUIRED_FIELDS = {"id", "question"}


def _validate_example(example: dict, line_number: int) -> None:
    missing = sorted(field for field in REQUIRED_FIELDS if not example.get(field))
    if missing:
        raise ValueError(f"Line {line_number}: missing required fields: {', '.join(missing)}")


def load_eval_dataset(path: str | Path) -> list[dict]:
    """Load an evaluation dataset from JSONL.

    Blank lines and lines starting with "#" are ignored. Each non-empty line must
    contain a JSON object with at least "id" and "question".
    """

    dataset_path = Path(path)
    examples: list[dict] = []
    with dataset_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            example = json.loads(stripped)
            if not isinstance(example, dict):
                raise ValueError(f"Line {line_number}: expected a JSON object")
            _validate_example(example, line_number)
            examples.append(example)
    return examples
