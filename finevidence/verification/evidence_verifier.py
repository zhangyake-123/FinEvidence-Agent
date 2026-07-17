"""Rule-based evidence support verifier for extracted claims."""

from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, InvalidOperation


VALUE_TOLERANCE = Decimal("0.000001")

STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "has",
    "into",
    "its",
    "not",
    "the",
    "this",
    "that",
    "was",
    "were",
    "with",
}


def _to_decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "").replace("%", ""))
    except (InvalidOperation, AttributeError, TypeError, ValueError):
        return None


def _values_match(left: object, right: object, tolerance: Decimal = VALUE_TOLERANCE) -> bool:
    left_value = _to_decimal(left)
    right_value = _to_decimal(right)
    if left_value is None or right_value is None:
        return False
    return abs(left_value - right_value) <= tolerance


def _source_table_ids(record: dict) -> list[str]:
    if "source_table_ids" in record:
        return [str(table_id) for table_id in record.get("source_table_ids", []) if table_id]
    table_id = record.get("source_table_id")
    return [str(table_id)] if table_id else []


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique_values.append(value)
    return unique_values


def _matches_identity(claim: dict, record: dict) -> bool:
    for field in ("ticker", "metric", "period"):
        expected = claim.get(field)
        if expected is None or expected == "":
            continue
        observed = record.get(field)
        if observed is None or str(observed) != str(expected):
            return False
    return True


def _matching_calculation(claim: dict, calculations: list[dict]) -> dict | None:
    for record in calculations:
        if not _matches_identity(claim, record):
            continue
        if claim.get("value") is not None and not _values_match(claim.get("value"), record.get("result")):
            continue
        if claim.get("display") and record.get("display") and str(claim.get("display")) != str(record.get("display")):
            continue
        return record
    return None


def _matching_fact(claim: dict, facts: list[dict]) -> dict | None:
    for record in facts:
        if not _matches_identity(claim, record):
            continue
        if claim.get("value") is not None and not _values_match(claim.get("value"), record.get("value")):
            continue
        return record
    return None


def _as_float(value: object) -> float | None:
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def _period_sort_key(period: object) -> tuple[int, str]:
    text = str(period)
    try:
        return int(text), text
    except ValueError:
        return 0, text


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


def _check_record(claim: dict, status: str, evidence_ids: list[str], reason: str) -> dict:
    return {
        "claim_id": claim.get("claim_id"),
        "claim_type": claim.get("claim_type"),
        "source": claim.get("source"),
        "claim": claim.get("claim"),
        "status": status,
        "evidence_ids": _unique(evidence_ids),
        "reason": reason,
    }


def _verify_calculation_claim(claim: dict, calculations: list[dict]) -> dict:
    record = _matching_calculation(claim, calculations)
    if record is None:
        return _check_record(claim, "unsupported", _source_table_ids(claim), "no_matching_calculation_record")

    evidence_ids = _unique(_source_table_ids(claim) + _source_table_ids(record))
    if not evidence_ids:
        return _check_record(claim, "ambiguous", evidence_ids, "matching_calculation_has_no_source_table")
    return _check_record(claim, "supported", evidence_ids, "claim_matches_calculation_and_source_tables")


def _trend_calculations(claim: dict, calculations: list[dict]) -> list[dict]:
    matching = [
        record
        for record in calculations
        if str(record.get("ticker", "")) == str(claim.get("ticker", ""))
        and str(record.get("metric", "")) == str(claim.get("metric", ""))
    ]
    by_period = {str(record.get("period")): record for record in matching}
    periods = [str(period) for period in claim.get("periods", []) if str(period) in by_period]
    if periods:
        return [by_period[period] for period in periods]
    return sorted(matching, key=lambda item: _period_sort_key(item.get("period")))


def _verify_trend_claim(claim: dict, calculations: list[dict]) -> dict:
    records = _trend_calculations(claim, calculations)
    expected_periods = [str(period) for period in claim.get("periods", [])]
    observed_periods = [str(record.get("period")) for record in records]
    if len(records) < 2:
        return _check_record(claim, "unsupported", _source_table_ids(claim), "not_enough_calculations_for_trend")
    if expected_periods and observed_periods != expected_periods:
        return _check_record(claim, "unsupported", _source_table_ids(claim), "missing_calculation_period_for_trend")

    observed_trend = _trend_label(records)
    if observed_trend != claim.get("trend"):
        return _check_record(claim, "unsupported", _source_table_ids(claim), "trend_direction_does_not_match_calculations")

    evidence_ids: list[str] = _source_table_ids(claim)
    for record in records:
        evidence_ids.extend(_source_table_ids(record))
    evidence_ids = _unique(evidence_ids)
    if not evidence_ids:
        return _check_record(claim, "ambiguous", evidence_ids, "trend_calculations_have_no_source_tables")
    return _check_record(claim, "supported", evidence_ids, "claim_trend_matches_calculations_and_source_tables")


def _verify_fact_claim(claim: dict, facts: list[dict]) -> dict:
    record = _matching_fact(claim, facts)
    if record is None:
        return _check_record(claim, "unsupported", _source_table_ids(claim), "no_matching_fact_record")

    evidence_ids = _unique(_source_table_ids(claim) + _source_table_ids(record))
    if not evidence_ids:
        return _check_record(claim, "ambiguous", evidence_ids, "matching_fact_has_no_source_table")
    return _check_record(claim, "supported", evidence_ids, "claim_matches_fact_and_source_table")


def _evidence_id(record: dict) -> str:
    for field in ("id", "source_table_id", "table_id", "chunk_id"):
        if record.get(field):
            return str(record[field])
    return ""


def _evidence_text(record: dict) -> str:
    parts = [
        record.get("id"),
        record.get("section"),
        record.get("text_preview"),
        record.get("content"),
        record.get("core_metrics"),
        record.get("rows_preview"),
    ]
    return " ".join(str(part) for part in parts if part)


def _tokens(text: object) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(text).lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def _verify_text_claim(claim: dict, evidence: list[dict]) -> dict:
    source_ids = set(_source_table_ids(claim))
    evidence_by_id = {_evidence_id(record): record for record in evidence if _evidence_id(record)}
    matched_ids = [evidence_id for evidence_id in source_ids if evidence_id in evidence_by_id]
    if matched_ids:
        return _check_record(claim, "supported", matched_ids, "claim_references_retrieved_evidence_id")

    claim_tokens = _tokens(claim.get("claim", ""))
    for record in evidence:
        evidence_tokens = _tokens(_evidence_text(record))
        overlap = claim_tokens & evidence_tokens
        if len(overlap) >= 4:
            return _check_record(claim, "supported", [_evidence_id(record)], "claim_text_overlaps_retrieved_evidence")

    if evidence:
        return _check_record(claim, "ambiguous", [], "retrieved_evidence_not_strictly_linked_to_claim")
    return _check_record(claim, "unsupported", [], "no_evidence_available")


def verify_claim(
    claim: dict,
    calculations: list[dict] | None = None,
    facts: list[dict] | None = None,
    evidence: list[dict] | None = None,
) -> dict:
    """Verify whether one extracted claim is supported by available evidence."""

    calculations = calculations or []
    facts = facts or []
    evidence = evidence or []

    if claim.get("claim_type") == "trend_claim" and claim.get("source") == "calculation":
        return _verify_trend_claim(claim, calculations)
    if claim.get("source") == "calculation":
        return _verify_calculation_claim(claim, calculations)
    if claim.get("source") == "fact":
        return _verify_fact_claim(claim, facts)
    return _verify_text_claim(claim, evidence)


def _aggregate_status(checks: list[dict]) -> str:
    if not checks:
        return "not_applicable"

    supported_count = sum(1 for check in checks if check.get("status") == "supported")
    unsupported_count = sum(1 for check in checks if check.get("status") == "unsupported")
    ambiguous_count = sum(1 for check in checks if check.get("status") == "ambiguous")

    if supported_count == len(checks):
        return "supported"
    if supported_count > 0:
        return "partially_supported"
    if unsupported_count > 0:
        return "unsupported"
    if ambiguous_count == len(checks):
        return "ambiguous"
    return "ambiguous"


def verify_evidence_support(
    claims: list[dict] | None = None,
    calculations: list[dict] | None = None,
    facts: list[dict] | None = None,
    evidence: list[dict] | None = None,
) -> dict:
    """Verify all extracted claims against calculations, facts, and retrieved evidence."""

    claim_checks = [
        verify_claim(
            claim,
            calculations=calculations,
            facts=facts,
            evidence=evidence,
        )
        for claim in (claims or [])
    ]
    return {
        "verifier": "EvidenceVerifier",
        "status": _aggregate_status(claim_checks),
        "claim_count": len(claim_checks),
        "supported_count": sum(1 for check in claim_checks if check.get("status") == "supported"),
        "unsupported_count": sum(1 for check in claim_checks if check.get("status") == "unsupported"),
        "ambiguous_count": sum(1 for check in claim_checks if check.get("status") == "ambiguous"),
        "claim_checks": claim_checks,
    }


def verify_evidence_support_from_payload(payload: dict) -> dict:
    return verify_evidence_support(
        claims=payload.get("claims", []),
        calculations=payload.get("calculations", []),
        facts=payload.get("facts", []),
        evidence=payload.get("evidence", []),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify claim support from a JSON payload.")
    parser.add_argument("payload", help="Path to a JSON file containing claims and evidence.")
    args = parser.parse_args()

    with open(args.payload, "r", encoding="utf-8") as file:
        payload = json.load(file)
    print(json.dumps(verify_evidence_support_from_payload(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
