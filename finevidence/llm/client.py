"""Provider-neutral LLM client wrappers for structured outputs."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from finevidence.config import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
)


class LLMClientError(RuntimeError):
    """Raised when the LLM client cannot generate a valid structured response."""


class JsonLLMClient(Protocol):
    """Minimal protocol used by LLMReportAgent."""

    def generate_json(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        schema: dict[str, Any],
        schema_name: str = "finevidence_report",
    ) -> dict:
        """Return one JSON object for the given prompt and schema."""


def _finevidence_api_key() -> str | None:
    return os.getenv("FINEVIDENCE_LLM_API_KEY")


def _load_openai_class():
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMClientError(
            "OpenAI SDK is not installed. Install the 'openai' package before using report_mode='llm'."
        ) from exc
    return OpenAI


def _load_litellm_completion():
    try:
        from litellm import completion
    except ImportError as exc:
        raise LLMClientError(
            "LiteLLM is not installed. Install the 'litellm' package before using FINEVIDENCE_LLM_PROVIDER=litellm."
        ) from exc
    return completion


def _env_api_key() -> str | None:
    return _finevidence_api_key() or os.getenv("OPENAI_API_KEY")


def _parse_json_object(text: str | None) -> dict:
    if not text:
        raise LLMClientError("LLM response did not include text content.")
    if not isinstance(text, str):
        raise LLMClientError("LLM response content must be a JSON string.")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMClientError("LLM response was not valid JSON.")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMClientError("LLM response was not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise LLMClientError("LLM response JSON must be an object.")
    return parsed


def _schema_prompt(system_prompt: str, schema: dict[str, Any]) -> str:
    return (
        f"{system_prompt}\n\n"
        "Return only one valid JSON object. It must match this JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )


def _chat_message_content(response: object) -> str | None:
    def normalize_content(content: object) -> str | None:
        if isinstance(content, str) or content is None:
            return content
        if isinstance(content, list):
            pieces: list[str] = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    pieces.append(part["text"])
                elif isinstance(part, str):
                    pieces.append(part)
            return "".join(pieces) if pieces else None
        return str(content)

    if isinstance(response, dict):
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            return normalize_content(message.get("content"))

    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        return normalize_content(getattr(message, "content", None))
    return None


class OpenAIResponsesLLMClient:
    """Small wrapper around the OpenAI Responses API.

    The OpenAI import is intentionally lazy so the deterministic pipeline and tests
    can run without the optional SDK installed.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    ) -> None:
        self.model = model or DEFAULT_LLM_MODEL
        self.api_key = api_key or _env_api_key()
        self.max_output_tokens = max_output_tokens
        self._client = None

    def _openai_client(self):
        if self._client is not None:
            return self._client

        if not self.api_key:
            raise LLMClientError(
                "FINEVIDENCE_LLM_API_KEY or OPENAI_API_KEY is not set. Set one before using report_mode='llm'."
            )

        OpenAI = _load_openai_class()
        self._client = OpenAI(api_key=self.api_key)
        return self._client

    def generate_json(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        schema: dict[str, Any],
        schema_name: str = "finevidence_report",
    ) -> dict:
        """Generate a JSON object that conforms to a JSON schema."""

        client = self._openai_client()
        response = client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False, indent=2),
                },
            ],
            max_output_tokens=self.max_output_tokens,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
        )

        return _parse_json_object(getattr(response, "output_text", None))


class OpenAICompatibleLLMClient:
    """Chat Completions client for OpenAI-compatible providers.

    This supports providers that expose OpenAI-compatible endpoints, such as many
    hosted open-source or third-party model APIs. It uses prompt-level schema
    instructions plus JSON object mode when the provider supports it.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS,
        json_mode: str | None = None,
    ) -> None:
        self.model = model or DEFAULT_LLM_MODEL
        self.api_key = api_key or _env_api_key() or "not-needed"
        self.base_url = base_url or DEFAULT_LLM_BASE_URL or None
        self.max_output_tokens = max_output_tokens
        self.json_mode = json_mode or os.getenv("FINEVIDENCE_LLM_JSON_MODE", "json_object")
        self._client = None

    def _chat_client(self):
        if self._client is not None:
            return self._client

        if not self.base_url:
            raise LLMClientError(
                "FINEVIDENCE_LLM_BASE_URL is required for FINEVIDENCE_LLM_PROVIDER=openai_compatible."
            )

        OpenAI = _load_openai_class()
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def generate_json(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        schema: dict[str, Any],
        schema_name: str = "finevidence_report",
    ) -> dict:
        """Generate a JSON object through an OpenAI-compatible chat endpoint."""

        client = self._chat_client()
        schema_prompt = _schema_prompt(system_prompt, schema)
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": schema_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False, indent=2),
                },
            ],
            "max_tokens": self.max_output_tokens,
        }
        if self.json_mode == "json_object":
            request["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**request)
        return _parse_json_object(_chat_message_content(response))


class LiteLLMClient:
    """Adapter for many LLM providers through LiteLLM.

    Use this when you want one interface for providers such as Anthropic, Gemini,
    OpenAI, Azure OpenAI, DeepSeek, or other LiteLLM-supported model backends.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS,
        json_mode: str | None = None,
    ) -> None:
        self.model = model or DEFAULT_LLM_MODEL
        self.api_key = api_key or _finevidence_api_key()
        self.base_url = base_url or DEFAULT_LLM_BASE_URL or None
        self.max_output_tokens = max_output_tokens
        self.json_mode = json_mode or os.getenv("FINEVIDENCE_LLM_JSON_MODE", "json_object")

    def generate_json(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        schema: dict[str, Any],
        schema_name: str = "finevidence_report",
    ) -> dict:
        """Generate a JSON object through LiteLLM."""

        completion = _load_litellm_completion()
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _schema_prompt(system_prompt, schema)},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False, indent=2),
                },
            ],
            "max_tokens": self.max_output_tokens,
        }
        if self.api_key:
            request["api_key"] = self.api_key
        if self.base_url:
            request["api_base"] = self.base_url
        if self.json_mode == "json_object":
            request["response_format"] = {"type": "json_object"}

        response = completion(**request)
        return _parse_json_object(_chat_message_content(response))


def create_llm_client(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS,
) -> JsonLLMClient:
    """Create an LLM client from provider config."""

    provider_name = (provider or DEFAULT_LLM_PROVIDER).strip().lower()
    if provider_name in {"openai", "openai_responses", "responses"}:
        return OpenAIResponsesLLMClient(
            model=model,
            api_key=api_key,
            max_output_tokens=max_output_tokens,
        )
    if provider_name in {"openai_compatible", "compatible", "chat_completions", "chat"}:
        return OpenAICompatibleLLMClient(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_output_tokens=max_output_tokens,
        )
    if provider_name in {"litellm", "lite", "multi", "multi_provider"}:
        return LiteLLMClient(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_output_tokens=max_output_tokens,
        )

    raise LLMClientError(
        "Unsupported LLM provider: "
        f"{provider_name}. Supported providers: openai, openai_compatible, litellm."
    )


OpenAILLMClient = OpenAIResponsesLLMClient
