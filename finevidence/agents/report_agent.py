"""Report agent for rendering calculation results into evidence-backed answers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from finevidence.agents.calculator_agent import CalculatorAgent
from finevidence.indexing.table_retriever import DEFAULT_TABLE_CHUNKS_PATH


DISCLAIMER = (
    "This system only retrieves, calculates, and organizes information from public disclosures. "
    "It does not provide investment advice."
)

METRIC_LABELS = {
    "gross_margin": "gross margin",
    "operating_margin": "operating margin",
    "net_margin": "net margin",
    "revenue_growth_yoy": "year-over-year revenue growth",
    "free_cash_flow": "free cash flow",
    "debt_to_assets": "debt-to-assets ratio",
    "gross_profit": "gross profit",
    "revenue": "revenue",
    "net_sales": "net sales",
    "operating_income": "operating income",
    "net_income": "net income",
    "operating_cash_flow": "operating cash flow",
    "capital_expenditure": "capital expenditure",
    "total_liabilities": "total liabilities",
    "total_assets": "total assets",
    "revenue_t": "current-period revenue",
    "revenue_t_minus_1": "prior-period revenue",
}


def _metric_label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric)


def _format_number(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    return str(value)


def _period_sort_key(period: str) -> tuple[int, str]:
    try:
        return int(period), period
    except ValueError:
        return 0, period


def _result_value(record: dict) -> float | None:
    value = record.get("result")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_citations(calculations: list[dict]) -> dict[str, str]:
    table_ids: list[str] = []
    for calculation in calculations:
        for table_id in calculation.get("source_table_ids", []):
            if table_id not in table_ids:
                table_ids.append(table_id)
    return {table_id: f"T{index + 1}" for index, table_id in enumerate(table_ids)}


def _citation_refs(record: dict, citations: dict[str, str]) -> str:
    refs = [f"[{citations[table_id]}]" for table_id in record.get("source_table_ids", []) if table_id in citations]
    return " ".join(refs)


def _group_by_metric(calculations: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for calculation in calculations:
        grouped.setdefault(str(calculation.get("metric", "")), []).append(calculation)
    for records in grouped.values():
        records.sort(key=lambda item: _period_sort_key(str(item.get("period", ""))))
    return grouped


def _trend_word(values: list[float]) -> str:
    if len(values) < 2:
        return "single-period result"

    increases = all(current >= previous for previous, current in zip(values, values[1:]))
    decreases = all(current <= previous for previous, current in zip(values, values[1:]))

    if increases and values[-1] > values[0]:
        return "increased overall"
    if decreases and values[-1] < values[0]:
        return "decreased overall"
    if values[-1] > values[0]:
        return "increased overall with some volatility"
    if values[-1] < values[0]:
        return "decreased overall with some volatility"
    return "was broadly flat"


def _build_conclusion(calculator_result: dict) -> str:
    calculations = calculator_result.get("calculations", [])
    if not calculations:
        return "There are not enough structured calculation results yet. More table evidence or metric extraction is needed."

    ticker = calculator_result.get("ticker") or "the company"
    grouped = _group_by_metric(calculations)

    if len(grouped) == 1:
        metric, records = next(iter(grouped.items()))
        label = _metric_label(metric)
        if len(records) == 1:
            record = records[0]
            return f"{ticker}'s {label} for {record.get('period')} was {record.get('display')}."

        values = [value for value in (_result_value(record) for record in records) if value is not None]
        first = records[0]
        last = records[-1]
        return (
            f"{ticker}'s {label} changed from {first.get('display')} in {first.get('period')} "
            f"to {last.get('display')} in {last.get('period')}, and {_trend_word(values)}."
        )

    latest_by_metric = []
    for metric, records in sorted(grouped.items()):
        latest = records[-1]
        latest_by_metric.append(f"{_metric_label(metric)} was {latest.get('display')} in {latest.get('period')}")
    return f"{ticker}'s key calculation results are: " + "; ".join(latest_by_metric) + "."


def _input_summary(inputs: dict) -> str:
    parts = []
    for name, metric in inputs.items():
        parts.append(f"{_metric_label(name)}={_format_number(metric.get('value'))}")
    return "; ".join(parts)


def _build_key_numbers(calculations: list[dict], citations: dict[str, str]) -> str:
    if not calculations:
        return "No key figures are available yet."

    lines = [
        "| Period | Metric | Inputs | Result | Source |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for record in sorted(calculations, key=lambda item: (str(item.get("metric", "")), _period_sort_key(str(item.get("period", ""))))):
        lines.append(
            "| {period} | {metric} | {inputs} | {display} | {refs} |".format(
                period=record.get("period", ""),
                metric=_metric_label(str(record.get("metric", ""))),
                inputs=_input_summary(record.get("inputs", {})),
                display=record.get("display", ""),
                refs=_citation_refs(record, citations),
            )
        )
    return "\n".join(lines)


def _build_calculation_steps(calculations: list[dict], citations: dict[str, str]) -> str:
    if not calculations:
        return "- No calculation steps are available yet."

    lines = []
    for record in sorted(calculations, key=lambda item: (str(item.get("metric", "")), _period_sort_key(str(item.get("period", ""))))):
        inputs = " / ".join(_format_number(metric.get("value")) for metric in record.get("inputs", {}).values())
        if str(record.get("metric")) == "revenue_growth_yoy":
            input_values = list(record.get("inputs", {}).values())
            if len(input_values) == 2:
                current = _format_number(input_values[0].get("value"))
                previous = _format_number(input_values[1].get("value"))
                inputs = f"({current} - {previous}) / {previous}"

        lines.append(
            "- {period} {metric}: {formula} = {inputs} = {display} {refs}".format(
                period=record.get("period", ""),
                metric=_metric_label(str(record.get("metric", ""))),
                formula=record.get("formula", ""),
                inputs=inputs,
                display=record.get("display", ""),
                refs=_citation_refs(record, citations),
            ).strip()
        )
    return "\n".join(lines)


def _build_evidence(citations: dict[str, str]) -> str:
    if not citations:
        return "- No table evidence citations are available yet."

    lines = []
    for table_id, ref in citations.items():
        lines.append(f"- [{ref}] {table_id}")
    return "\n".join(lines)


def _warning_text(warning: dict) -> str:
    if "missing_metrics" in warning:
        missing = ", ".join(warning.get("missing_metrics", []))
        return f"{warning.get('period', 'unknown period')} is missing metrics: {missing}"
    if warning.get("reason") == "division_by_zero":
        return f"{warning.get('period', 'unknown period')} has a zero denominator, so {warning.get('calculation')} cannot be calculated"
    if warning.get("reason") == "not_enough_periods":
        periods = ", ".join(warning.get("available_periods", []))
        return f"not enough periods are available; current periods: {periods or 'none'}"
    return json.dumps(warning, ensure_ascii=False)


def _build_verification(calculator_result: dict) -> str:
    warnings = calculator_result.get("warnings", [])
    calculations = calculator_result.get("calculations", [])

    if not calculations:
        return "- Numeric consistency: failed because no calculable results are available.\n- Citation support: insufficient evidence.\n- Uncertainty: high."

    if not warnings:
        return "- Numeric consistency: passed by rule-based calculation.\n- Citation support: source table IDs are preserved.\n- Uncertainty: low."

    lines = [
        "- Numeric consistency: some items need review.",
        "- Citation support: source table IDs are preserved, but some metrics are missing or not calculable.",
        "- Uncertainty: medium.",
    ]
    for warning in warnings:
        lines.append(f"- Warning: {_warning_text(warning)}")
    return "\n".join(lines)


class ReportAgent:
    """Render calculator outputs into a concise evidence-backed report."""

    def __init__(self, calculator_agent: CalculatorAgent | None = None) -> None:
        self.calculator_agent = calculator_agent

    @classmethod
    def from_processed(cls, table_path: str | Path = DEFAULT_TABLE_CHUNKS_PATH) -> "ReportAgent":
        return cls(CalculatorAgent.from_processed(table_path))

    def render(self, calculator_result: dict) -> str:
        calculations = calculator_result.get("calculations", [])
        citations = _collect_citations(calculations)

        sections = [
            "## Conclusion",
            _build_conclusion(calculator_result),
            "",
            "## Key Figures",
            _build_key_numbers(calculations, citations),
            "",
            "## Calculation Steps",
            _build_calculation_steps(calculations, citations),
            "",
            "## Evidence",
            _build_evidence(citations),
            "",
            "## Checks and Uncertainty",
            _build_verification(calculator_result),
            "",
            "## Disclaimer",
            DISCLAIMER,
        ]
        return "\n".join(sections)

    def run(
        self,
        question: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_k: int = 5,
    ) -> dict:
        if self.calculator_agent is None:
            raise ValueError("ReportAgent.run requires a CalculatorAgent. Use from_processed().")

        calculator_result = self.calculator_agent.run(
            question,
            ticker=ticker,
            fiscal_year=fiscal_year,
            top_k=top_k,
        )
        return {
            "agent": "ReportAgent",
            "question": question,
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "calculator_result": calculator_result,
            "report": self.render(calculator_result),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ReportAgent.")
    parser.add_argument("question", help="Question to answer with a report.")
    parser.add_argument("--ticker", default=None, help="Optional ticker filter, e.g. AAPL.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year filter.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of tables to inspect.")
    parser.add_argument("--tables", default=DEFAULT_TABLE_CHUNKS_PATH, help="Path to table_chunks.jsonl.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    agent = ReportAgent.from_processed(args.tables)
    result = agent.run(args.question, ticker=args.ticker, fiscal_year=args.year, top_k=args.top_k)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["report"])


if __name__ == "__main__":
    main()
