"""LLM-backed report agent for evidence-grounded answer generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from finevidence.agents.report_agent import DISCLAIMER, _format_number, _metric_label
from finevidence.llm.client import create_llm_client
from finevidence.llm.prompts import LLM_REPORT_SCHEMA, LLM_REPORT_SYSTEM_PROMPT


def _period_sort_key(period: object) -> tuple[int, str]:
    text = str(period)
    try:
        return int(text), text
    except ValueError:
        return 0, text


def _as_float(value: object) -> float | None:
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def _source_table_ids(record: dict) -> list[str]:
    ids = [str(table_id) for table_id in record.get("source_table_ids", []) if table_id]
    if record.get("source_table_id"):
        ids.append(str(record["source_table_id"]))

    inputs = record.get("inputs", {})
    if isinstance(inputs, dict):
        for metric in inputs.values():
            if isinstance(metric, dict) and metric.get("source_table_id"):
                ids.append(str(metric["source_table_id"]))
    return _unique(ids)


def _evidence_id(record: dict) -> str:
    for field in ("id", "source_table_id", "table_id", "chunk_id"):
        if record.get(field):
            return str(record[field])
    return ""


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            output.append(value)
    return output


def _format_delta(metric: str, delta: float) -> str:
    if metric.endswith("margin") or metric in {"gross_margin", "operating_margin", "net_margin", "debt_to_assets"}:
        return f"{delta * 100:.2f} percentage points"
    if metric == "revenue_growth_yoy":
        return f"{delta * 100:.2f} percentage points"
    return _format_number(delta)


def _trend_direction(values: list[float]) -> str:
    if len(values) < 2:
        return "single_period"
    increases = all(current >= previous for previous, current in zip(values, values[1:]))
    decreases = all(current <= previous for previous, current in zip(values, values[1:]))
    if increases and values[-1] > values[0]:
        return "steadily_improved"
    if decreases and values[-1] < values[0]:
        return "steadily_declined"
    if values[-1] > values[0]:
        return "improved_with_volatility"
    if values[-1] < values[0]:
        return "declined_with_volatility"
    return "flat"


def build_trend_insights(calculations: list[dict]) -> list[dict]:
    """Build deterministic trend facts that the LLM can verbalize."""

    grouped: dict[tuple[str, str], list[dict]] = {}
    for record in calculations:
        key = (str(record.get("ticker", "")), str(record.get("metric", "")))
        grouped.setdefault(key, []).append(record)

    insights: list[dict] = []
    for (ticker, metric), records in sorted(grouped.items()):
        records = sorted(records, key=lambda item: _period_sort_key(item.get("period", "")))
        values = [_as_float(record.get("result")) for record in records]
        if any(value is None for value in values) or len(values) < 2:
            continue

        numeric_values = [value for value in values if value is not None]
        intervals: list[dict] = []
        for previous, current in zip(records, records[1:]):
            previous_value = _as_float(previous.get("result"))
            current_value = _as_float(current.get("result"))
            if previous_value is None or current_value is None:
                continue
            delta = current_value - previous_value
            intervals.append(
                {
                    "from_period": str(previous.get("period")),
                    "to_period": str(current.get("period")),
                    "delta": round(delta, 6),
                    "delta_display": _format_delta(metric, delta),
                }
            )

        largest_increase = None
        positive_intervals = [interval for interval in intervals if float(interval["delta"]) > 0]
        if positive_intervals:
            largest_increase = max(positive_intervals, key=lambda item: float(item["delta"]))

        insights.append(
            {
                "ticker": ticker,
                "metric": metric,
                "metric_label": _metric_label(metric),
                "periods": [str(record.get("period")) for record in records],
                "displays": [str(record.get("display")) for record in records],
                "direction": _trend_direction(numeric_values),
                "is_steady_improvement": all(float(interval["delta"]) > 0 for interval in intervals) if intervals else False,
                "is_steady_decline": all(float(interval["delta"]) < 0 for interval in intervals) if intervals else False,
                "intervals": intervals,
                "largest_increase_interval": largest_increase,
            }
        )
    return insights


def collect_available_evidence_ids(payload: dict) -> list[str]:
    """Collect ids the LLM is allowed to cite."""

    ids: list[str] = []
    for record in payload.get("evidence", []):
        evidence_id = _evidence_id(record)
        if evidence_id:
            ids.append(evidence_id)
    for record in payload.get("calculations", []):
        ids.extend(_source_table_ids(record))
    for record in payload.get("facts", []):
        ids.extend(_source_table_ids(record))
    return _unique(ids)


def _citation_sort_key(citation: dict) -> tuple[str, str]:
    marker = str(citation.get("marker", ""))
    return marker.strip("[]").upper(), str(citation.get("evidence_id", ""))


def _normalize_marker(marker: object, index: int) -> str:
    text = str(marker or "").strip()
    text = text.strip("[]")
    return text.upper() if text else f"T{index}"


def _normalize_citations(citations: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for index, citation in enumerate(citations, start=1):
        if not isinstance(citation, dict):
            continue
        evidence_id = str(citation.get("evidence_id", "")).strip()
        if not evidence_id:
            continue
        normalized.append(
            {
                "marker": _normalize_marker(citation.get("marker"), index),
                "evidence_id": evidence_id,
            }
        )
    return sorted(normalized, key=_citation_sort_key)


def _evidence_section(citations: list[dict]) -> str:
    if not citations:
        return ""
    lines = ["## Evidence"]
    for citation in citations:
        lines.append(f"- [{citation['marker']}] {citation['evidence_id']}")
    return "\n".join(lines)


def _ensure_evidence_section(answer: str, citations: list[dict]) -> str:
    if "## Evidence" in answer or not citations:
        return answer.strip()
    return f"{answer.strip()}\n\n{_evidence_section(citations)}"


def build_llm_payload(
    question: str,
    question_type: str,
    ticker: str | None,
    fiscal_year: int | None,
    evidence: list[dict] | None = None,
    calculations: list[dict] | None = None,
    facts: list[dict] | None = None,
    warnings: list[dict] | list[str] | None = None,
    fallback_report: str | None = None,
) -> dict[str, Any]:
    """Build a compact, structured payload for report generation."""

    payload: dict[str, Any] = {
        "question": question,
        "question_type": question_type,
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "evidence": evidence or [],
        "calculations": calculations or [],
        "facts": facts or [],
        "warnings": warnings or [],
        "trend_insights": build_trend_insights(calculations or []),
        "fallback_rule_report": fallback_report or "",
        "disclaimer": DISCLAIMER,
    }
    payload["available_evidence_ids"] = collect_available_evidence_ids(payload)
    return payload


class LLMReportAgent:
    """Generate final Markdown answers from structured FinEvidence payloads."""

    def __init__(
        self,
        llm_client: object | None = None,
        model: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.llm_client = llm_client or create_llm_client(
            provider=provider,
            model=model,
            base_url=base_url,
        )

    def render_payload(self, payload: dict[str, Any]) -> dict:
        """Generate and normalize one LLM report."""

        enriched_payload = dict(payload)
        enriched_payload.setdefault("available_evidence_ids", collect_available_evidence_ids(enriched_payload))
        enriched_payload.setdefault("trend_insights", build_trend_insights(enriched_payload.get("calculations", [])))

        raw_response = self.llm_client.generate_json(
            system_prompt=LLM_REPORT_SYSTEM_PROMPT,
            user_payload=enriched_payload,
            schema=LLM_REPORT_SCHEMA,
            schema_name="finevidence_report",
        )
        citations = _normalize_citations(raw_response.get("citations", []))
        answer = str(raw_response.get("answer_markdown", "")).strip()
        answer = _ensure_evidence_section(answer, citations)

        return {
            "agent": "LLMReportAgent",
            "report": answer,
            "used_evidence_ids": _unique([str(value) for value in raw_response.get("used_evidence_ids", [])]),
            "citations": citations,
            "limitations": [str(value) for value in raw_response.get("limitations", [])],
            "raw_response": raw_response,
            "prompt_payload_summary": {
                "question_type": enriched_payload.get("question_type"),
                "evidence_count": len(enriched_payload.get("evidence", [])),
                "calculation_count": len(enriched_payload.get("calculations", [])),
                "fact_count": len(enriched_payload.get("facts", [])),
                "available_evidence_count": len(enriched_payload.get("available_evidence_ids", [])),
                "trend_insight_count": len(enriched_payload.get("trend_insights", [])),
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LLMReportAgent on a structured JSON payload.")
    parser.add_argument("payload", help="Path to a JSON file containing question, evidence, facts, and calculations.")
    args = parser.parse_args()

    with open(args.payload, "r", encoding="utf-8") as file:
        payload = json.load(file)
    result = LLMReportAgent().render_payload(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
