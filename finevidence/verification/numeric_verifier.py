"""Rule-based numeric verifier for financial calculations and fact answers."""

from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


PERCENTAGE_METRICS = {
    "gross_margin",
    "operating_margin",
    "net_margin",
    "revenue_growth_yoy",
    "debt_to_assets",
}

RESULT_TOLERANCE = Decimal("0.00001")


def _to_decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "").replace("%", ""))
    except (InvalidOperation, AttributeError, TypeError, ValueError):
        return None


def _round_decimal(value: Decimal, places: str = "0.000001") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _numeric_status(checks: list[dict]) -> str:
    if not checks:
        return "insufficient_data"
    if any(check.get("status") == "numeric_error" for check in checks):
        return "numeric_error"
    if any(check.get("status") in {"missing_input", "unsupported"} for check in checks):
        return "insufficient_data"
    return "passed"


def _check(name: str, status: str, **details: object) -> dict:
    record = {"check": name, "status": status}
    if details:
        record["details"] = details
    return record


def _input_value(inputs: dict, name: str) -> Decimal | None:
    metric = inputs.get(name)
    if not isinstance(metric, dict):
        return None
    return _to_decimal(metric.get("value"))


def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return numerator / denominator


def recompute_calculation(record: dict) -> Decimal | None:
    """Recompute a supported calculation record from its input values."""

    metric = record.get("metric")
    inputs = record.get("inputs", {})

    if metric == "gross_margin":
        numerator = _input_value(inputs, "gross_profit")
        denominator = _input_value(inputs, "revenue")
    elif metric == "operating_margin":
        numerator = _input_value(inputs, "operating_income")
        denominator = _input_value(inputs, "revenue")
    elif metric == "net_margin":
        numerator = _input_value(inputs, "net_income")
        denominator = _input_value(inputs, "revenue")
    elif metric == "debt_to_assets":
        numerator = _input_value(inputs, "total_liabilities")
        denominator = _input_value(inputs, "total_assets")
    elif metric == "revenue_growth_yoy":
        current = _input_value(inputs, "revenue_t")
        previous = _input_value(inputs, "revenue_t_minus_1")
        if current is None or previous is None:
            return None
        return _safe_divide(current - previous, previous)
    elif metric == "free_cash_flow":
        operating_cash_flow = _input_value(inputs, "operating_cash_flow")
        capital_expenditure = _input_value(inputs, "capital_expenditure")
        if operating_cash_flow is None or capital_expenditure is None:
            return None
        return operating_cash_flow - capital_expenditure
    else:
        return None

    if numerator is None or denominator is None:
        return None
    return _safe_divide(numerator, denominator)


def _expected_display(metric: str, recomputed: Decimal) -> str:
    if metric in PERCENTAGE_METRICS:
        return f"{_round_decimal(recomputed * Decimal('100'), '0.01')}%"

    rounded = _round_decimal(recomputed, "0.01")
    if rounded == rounded.to_integral_value():
        return f"{int(rounded):,}"
    return f"{rounded:,}"


def _display_to_decimal(metric: str, display: object) -> Decimal | None:
    value = _to_decimal(display)
    if value is None:
        return None
    if metric in PERCENTAGE_METRICS:
        return value / Decimal("100")
    return value


def verify_calculation(record: dict, tolerance: Decimal = RESULT_TOLERANCE) -> dict:
    """Verify one derived calculation record."""

    checks: list[dict] = []
    metric = str(record.get("metric", ""))
    recomputed = recompute_calculation(record)
    reported_result = _to_decimal(record.get("result"))

    if recomputed is None:
        checks.append(_check("formula_result", "unsupported", reason="unsupported_formula_or_missing_input"))
    elif reported_result is None:
        checks.append(_check("formula_result", "missing_input", reason="missing_reported_result"))
    else:
        rounded_recomputed = _round_decimal(recomputed)
        difference = abs(rounded_recomputed - reported_result)
        status = "passed" if difference <= tolerance else "numeric_error"
        checks.append(
            _check(
                "formula_result",
                status,
                expected=float(rounded_recomputed),
                observed=float(reported_result),
                difference=float(difference),
            )
        )

    display_value = _display_to_decimal(metric, record.get("display"))
    if recomputed is None:
        checks.append(_check("display", "unsupported", reason="cannot_check_display_without_recomputed_value"))
    elif display_value is None:
        checks.append(_check("display", "missing_input", reason="missing_or_invalid_display"))
    else:
        display_difference = abs(_round_decimal(recomputed) - _round_decimal(display_value))
        status = "passed" if display_difference <= Decimal("0.0001") else "numeric_error"
        checks.append(
            _check(
                "display",
                status,
                expected=_expected_display(metric, recomputed),
                observed=record.get("display"),
                difference=float(display_difference),
            )
        )

    source_table_ids = record.get("source_table_ids", [])
    checks.append(
        _check(
            "source_tables",
            "passed" if source_table_ids else "missing_input",
            source_table_ids=source_table_ids,
        )
    )

    return {
        "type": "calculation",
        "metric": metric,
        "ticker": record.get("ticker"),
        "period": record.get("period"),
        "status": _numeric_status(checks),
        "checks": checks,
    }


def _normalized_text(value: object) -> str:
    return re.sub(r"[^0-9.\-]", "", str(value))


def _answer_contains_fact_value(answer: str, fact: dict) -> bool:
    value = fact.get("value")
    normalized_value = _normalized_text(value)
    if not normalized_value:
        return False

    answer_numbers = {_normalized_text(match.group(0)) for match in re.finditer(r"-?\d[\d,]*(?:\.\d+)?", answer)}
    return normalized_value in answer_numbers


def verify_fact(fact: dict, answer: str | None = None) -> dict:
    """Verify one raw metric fact record."""

    checks: list[dict] = []
    value = _to_decimal(fact.get("value"))
    checks.append(_check("fact_value", "passed" if value is not None else "missing_input", value=fact.get("value")))
    checks.append(_check("period", "passed" if fact.get("period") else "missing_input", period=fact.get("period")))
    checks.append(_check("source_table", "passed" if fact.get("source_table_id") else "missing_input", source_table_id=fact.get("source_table_id")))
    checks.append(_check("source_label", "passed" if fact.get("source_label") else "missing_input", source_label=fact.get("source_label")))

    if answer is not None:
        checks.append(
            _check(
                "answer_contains_value",
                "passed" if _answer_contains_fact_value(answer, fact) else "numeric_error",
                value=fact.get("value"),
            )
        )

    return {
        "type": "fact",
        "metric": fact.get("metric"),
        "ticker": fact.get("ticker"),
        "period": fact.get("period"),
        "status": _numeric_status(checks),
        "checks": checks,
    }


def verify_numeric_outputs(
    calculations: list[dict] | None = None,
    facts: list[dict] | None = None,
    answer: str | None = None,
) -> dict:
    """Verify calculations and fact records, returning an aggregate report."""

    calculation_checks = [verify_calculation(record) for record in (calculations or [])]
    fact_checks = [verify_fact(record, answer=answer) for record in (facts or [])]
    all_checks = calculation_checks + fact_checks
    issues = [check for check in all_checks if check.get("status") != "passed"]

    if not all_checks:
        status = "not_applicable"
    elif any(check.get("status") == "numeric_error" for check in issues):
        status = "numeric_error"
    elif issues:
        status = "insufficient_data"
    else:
        status = "passed"

    return {
        "verifier": "NumericVerifier",
        "status": status,
        "checked_calculations": len(calculation_checks),
        "checked_facts": len(fact_checks),
        "issue_count": len(issues),
        "issues": issues,
        "calculation_checks": calculation_checks,
        "fact_checks": fact_checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify numeric outputs from a JSON payload.")
    parser.add_argument("payload", help="Path to a JSON payload from the orchestrator.")
    args = parser.parse_args()

    with open(args.payload, "r", encoding="utf-8") as file:
        payload = json.load(file)

    report = verify_numeric_outputs(
        calculations=payload.get("calculations", []),
        facts=payload.get("facts", []),
        answer=payload.get("answer"),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
