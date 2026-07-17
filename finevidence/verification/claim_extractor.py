"""Rule-based claim extraction from structured FinEvidence outputs."""

from __future__ import annotations

import argparse
import json
import re


METRIC_LABELS = {
    "gross_margin": "gross margin",
    "operating_margin": "operating margin",
    "net_margin": "net margin",
    "revenue_growth_yoy": "year-over-year revenue growth",
    "free_cash_flow": "free cash flow",
    "debt_to_assets": "debt-to-assets ratio",
    "gross_profit": "gross profit",
    "revenue": "revenue",
    "operating_income": "operating income",
    "net_income": "net income",
    "operating_cash_flow": "operating cash flow",
    "total_assets": "total assets",
    "total_liabilities": "total liabilities",
    "cash_and_cash_equivalents": "cash and cash equivalents",
}


def _metric_label(metric: object) -> str:
    return METRIC_LABELS.get(str(metric), str(metric))


def _format_value(value: object) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    return str(value)


def _period_sort_key(period: object) -> tuple[int, str]:
    text = str(period)
    try:
        return int(text), text
    except ValueError:
        return 0, text


def _claim_id(prefix: str, index: int) -> str:
    return f"{prefix}_{index:04d}"


def _as_float(value: object) -> float | None:
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def _source_table_ids(record: dict) -> list[str]:
    if "source_table_ids" in record:
        return [str(table_id) for table_id in record.get("source_table_ids", []) if table_id]
    table_id = record.get("source_table_id")
    return [str(table_id)] if table_id else []


def _calculation_numeric_claim(record: dict, index: int) -> dict:
    metric = str(record.get("metric", ""))
    ticker = record.get("ticker") or "The company"
    period = record.get("period")
    display = record.get("display")
    label = _metric_label(metric)
    claim = f"{ticker}'s {label} was {display} in {period}."
    return {
        "claim_id": _claim_id("calc", index),
        "claim_type": "numeric_claim",
        "claim": claim,
        "source": "calculation",
        "ticker": record.get("ticker"),
        "metric": metric,
        "period": str(period),
        "value": record.get("result"),
        "display": display,
        "formula": record.get("formula"),
        "source_table_ids": _source_table_ids(record),
    }


def _group_calculations(calculations: list[dict]) -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for record in calculations:
        key = (str(record.get("ticker", "")), str(record.get("metric", "")))
        grouped.setdefault(key, []).append(record)
    for records in grouped.values():
        records.sort(key=lambda item: _period_sort_key(item.get("period")))
    return grouped


def _trend_label(records: list[dict]) -> str:
    values = [_as_float(record.get("result")) for record in records]
    values = [value for value in values if value is not None]
    if len(values) < 2:
        return "single_period"

    nondecreasing = all(current >= previous for previous, current in zip(values, values[1:]))
    nonincreasing = all(current <= previous for previous, current in zip(values, values[1:]))
    if nondecreasing and values[-1] > values[0]:
        return "increased"
    if nonincreasing and values[-1] < values[0]:
        return "decreased"
    if values[-1] > values[0]:
        return "increased_with_volatility"
    if values[-1] < values[0]:
        return "decreased_with_volatility"
    return "flat"


def _trend_phrase(trend: str) -> str:
    return {
        "increased": "increased",
        "decreased": "decreased",
        "increased_with_volatility": "increased overall with some volatility",
        "decreased_with_volatility": "decreased overall with some volatility",
        "flat": "was broadly flat",
    }.get(trend, "had a single-period result")


def _calculation_trend_claim(records: list[dict], index: int) -> dict | None:
    if len(records) < 2:
        return None

    first = records[0]
    last = records[-1]
    metric = str(first.get("metric", ""))
    ticker = first.get("ticker") or "The company"
    label = _metric_label(metric)
    trend = _trend_label(records)
    source_table_ids: list[str] = []
    for record in records:
        for table_id in _source_table_ids(record):
            if table_id not in source_table_ids:
                source_table_ids.append(table_id)

    claim = (
        f"{ticker}'s {label} {_trend_phrase(trend)} from "
        f"{first.get('display')} in {first.get('period')} to {last.get('display')} in {last.get('period')}."
    )
    return {
        "claim_id": _claim_id("trend", index),
        "claim_type": "trend_claim",
        "claim": claim,
        "source": "calculation",
        "ticker": first.get("ticker"),
        "metric": metric,
        "trend": trend,
        "periods": [str(record.get("period")) for record in records],
        "start_period": str(first.get("period")),
        "end_period": str(last.get("period")),
        "start_display": first.get("display"),
        "end_display": last.get("display"),
        "source_table_ids": source_table_ids,
    }


def _fact_numeric_claim(record: dict, index: int) -> dict:
    metric = str(record.get("metric", ""))
    ticker = record.get("ticker") or "The company"
    period = record.get("period")
    value = _format_value(record.get("value"))
    label = _metric_label(metric)
    claim = f"{ticker}'s {label} was {value} in {period}."
    return {
        "claim_id": _claim_id("fact", index),
        "claim_type": "numeric_claim",
        "claim": claim,
        "source": "fact",
        "ticker": record.get("ticker"),
        "metric": metric,
        "period": str(period),
        "value": record.get("value"),
        "display": value,
        "source_table_ids": _source_table_ids(record),
        "source_label": record.get("source_label"),
    }


def _answer_numeric_claims(answer: str | None, start_index: int) -> list[dict]:
    """Extract fallback numeric claims from answer text when no structured data exists."""

    if not answer:
        return []

    claims: list[dict] = []
    sentences = re.split(r"(?<=[.!?])\s+", answer.replace("\n", " "))
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or sentence.startswith("#"):
            continue
        if not re.search(r"\d", sentence):
            continue
        claims.append(
            {
                "claim_id": _claim_id("answer", start_index + len(claims)),
                "claim_type": "numeric_claim",
                "claim": sentence,
                "source": "answer_text",
                "ticker": None,
                "metric": None,
                "period": None,
                "value": None,
                "display": None,
                "source_table_ids": [],
            }
        )
    return claims


def extract_claims(
    answer: str | None = None,
    calculations: list[dict] | None = None,
    facts: list[dict] | None = None,
) -> list[dict]:
    """Extract structured claims from calculations, facts, and fallback answer text."""

    claims: list[dict] = []
    calculations = calculations or []
    facts = facts or []

    for record in calculations:
        claims.append(_calculation_numeric_claim(record, len(claims) + 1))

    for records in _group_calculations(calculations).values():
        trend_claim = _calculation_trend_claim(records, len(claims) + 1)
        if trend_claim is not None:
            claims.append(trend_claim)

    for record in facts:
        claims.append(_fact_numeric_claim(record, len(claims) + 1))

    if not claims:
        claims.extend(_answer_numeric_claims(answer, 1))

    return claims


def extract_claims_from_payload(payload: dict) -> dict:
    claims = extract_claims(
        answer=payload.get("answer"),
        calculations=payload.get("calculations", []),
        facts=payload.get("facts", []),
    )
    return {
        "extractor": "ClaimExtractor",
        "claim_count": len(claims),
        "claims": claims,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract claims from an orchestrator JSON payload.")
    parser.add_argument("payload", help="Path to a JSON payload from the orchestrator.")
    args = parser.parse_args()

    with open(args.payload, "r", encoding="utf-8") as file:
        payload = json.load(file)

    print(json.dumps(extract_claims_from_payload(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
