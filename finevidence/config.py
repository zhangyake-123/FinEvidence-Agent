"""Project-level configuration for FinEvidence-Agent."""

from __future__ import annotations

import os
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _strip_inline_comment(value: str) -> str:
    quote: str | None = None
    for index, char in enumerate(value):
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        elif char == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_env_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("export "):
        text = text[len("export ") :].lstrip()

    key, separator, value = text.partition("=")
    if not separator:
        return None

    key = key.strip()
    if not key or any(char.isspace() for char in key):
        return None

    value = _strip_inline_comment(value.strip())
    return key, _strip_quotes(value)


def load_env_file(path: str | Path | None = None) -> dict[str, str]:
    """Load .env values into os.environ without overriding existing variables."""

    env_path = Path(path) if path is not None else _project_root() / ".env"
    if not env_path.exists():
        return {}

    loaded: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        key, value = parsed
        if key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


load_env_file()

DEFAULT_LLM_MODEL = os.getenv("FINEVIDENCE_LLM_MODEL", "gpt-4o-mini")
DEFAULT_LLM_PROVIDER = os.getenv("FINEVIDENCE_LLM_PROVIDER", "openai")
DEFAULT_LLM_BASE_URL = os.getenv("FINEVIDENCE_LLM_BASE_URL", "")
DEFAULT_LLM_MAX_OUTPUT_TOKENS = int(os.getenv("FINEVIDENCE_LLM_MAX_OUTPUT_TOKENS", "1600"))
DEFAULT_REPORT_MODE = os.getenv("FINEVIDENCE_REPORT_MODE", "rule")
