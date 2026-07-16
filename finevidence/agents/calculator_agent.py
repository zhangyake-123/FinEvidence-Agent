"""Calculator agent for deterministic financial metric calculations."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from finevidence.agents.table_agent import TableAgent, extract_metrics_from_table, infer_requested_periods
from finevidence.indexing.table_retriever import DEFAULT_TABLE_CHUNKS_PATH


CALCULATION_INPUTS = {
    "gross_margin": ("gross_profit", "revenue"),
    "operating_margin": ("operating_income", "revenue"),
    "net_margin": ("net_income", "revenue"),
    "revenue_growth_yoy": ("revenue",),
    "free_cash_flow": ("operating_cash_flow", "capital_expenditure"),
    "debt_to_assets": ("total_liabilities", "total_assets"),
}

CALCULATION_FORMULAS = {
    "gross_margin": "gross_profit / revenue",
    "operating_margin": "operating_income / revenue",
    "net_margin": "net_income / revenue",
    "revenue_growth_yoy": "(revenue_t - revenue_t_minus_1) / revenue_t_minus_1",
    "free_cash_flow": "operating_cash_flow - capital_expenditure",
    "debt_to_assets": "total_liabilities / total_assets",
}

PERCENTAGE_CALCULATIONS = {
    "gross_margin",
    "operating_margin",
    "net_margin",
    "revenue_growth_yoy",
    "debt_to_assets",
}


def infer_requested_calculations(question: str) -> set[str]:
    """Infer the financial calculations requested by a user question."""

    query = question.lower()
    calculations: set[str] = set()

    if "gross margin" in query or "毛利率" in query:
        calculations.add("gross_margin")
    if "operating margin" in query or "经营利润率" in query:
        calculations.add("operating_margin")
    if "net margin" in query or "净利率" in query:
        calculations.add("net_margin")
    if (
        "revenue growth" in query
        or "sales growth" in query
        or "yoy" in query
        or "year over year" in query
        or "同比" in query
        or "收入增长" in query
    ):
        calculations.add("revenue_growth_yoy")
    if "free cash flow" in query or "fcf" in query or "自由现金流" in query:
        calculations.add("free_cash_flow")
    if "debt to assets" in query or "liabilities to assets" in query or "资产负债率" in query:
        calculations.add("debt_to_assets")

    return calculations or {"gross_margin"}


def required_metrics(calculations: set[str]) -> set[str]:
    """Return the raw metrics needed for a set of calculations."""

    metrics: set[str] = set()
    for calculation in calculations:
        metrics.update(CALCULATION_INPUTS.get(calculation, ()))
    return metrics


def _to_decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _round_decimal(value: Decimal, places: str = "0.000001") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _display_percentage(value: Decimal) -> str:
    percent = _round_decimal(value * Decimal("100"), "0.01")
    return f"{percent}%"


def _display_number(value: Decimal) -> str:
    rounded = _round_decimal(value, "0.01")
    if rounded == rounded.to_integral_value():
        return f"{int(rounded):,}"
    return f"{rounded:,}"


def _period_sort_key(period: str) -> tuple[int, str]:
    try:
        return int(period), period
    except ValueError:
        return 0, period


def _metric_source_id(metric: dict) -> str:
    parts = [
        str(metric.get("ticker", "")),
        str(metric.get("period", "")),
        str(metric.get("metric", "")),
        str(metric.get("source_table_id", "")),
        f"r{metric.get('source_row_index', '')}",
        f"c{metric.get('source_column_index', '')}",
    ]
    return "_".join(part for part in parts if part)


def _label_quality(metric: dict) -> float:
    name = str(metric.get("metric", ""))
    label = str(metric.get("source_label", "")).lower()

    if name == "revenue":
        if label in {"revenue", "total revenue", "net sales", "total net sales"}:
            return 10.0
        if "deferred revenue" in label or "unearned revenue" in label:
            return -10.0
    if name == "gross_profit" and label in {"gross margin", "gross profit", "total gross margin"}:
        return 8.0
    if name == "operating_income" and label == "operating income":
        return 8.0
    if name == "net_income" and label == "net income":
        return 8.0
    return 0.0


def _metric_rank(metric: dict) -> tuple[float, float, float]:
    return (
        _label_quality(metric),
        float(metric.get("source_table_score", 0.0)),
        float(len(metric.get("source_core_metrics", []))),
    )


def _group_metrics(metrics: list[dict]) -> dict[tuple[str, str], dict[str, dict]]:
    grouped: dict[tuple[str, str], dict[str, dict]] = {}
    for metric in metrics:
        value = _to_decimal(metric.get("value"))
        if value is None:
            continue
        key = (str(metric.get("ticker", "")), str(metric.get("period", "")))
        name = str(metric.get("metric", ""))
        record = dict(metric)
        record["decimal_value"] = value

        by_metric = grouped.setdefault(key, {})
        if name not in by_metric or _metric_rank(record) > _metric_rank(by_metric[name]):
            by_metric[name] = record
    return grouped


def _calculation_record(
    calculation: str,
    ticker: str,
    period: str,
    result: Decimal,
    inputs: dict[str, dict],
) -> dict:
    rounded_result = _round_decimal(result)
    source_table_ids = sorted(
        {
            str(metric.get("source_table_id"))
            for metric in inputs.values()
            if metric.get("source_table_id")
        }
    )
    return {
        "metric": calculation,
        "ticker": ticker,
        "period": period,
        "formula": CALCULATION_FORMULAS[calculation],
        "inputs": {
            name: {
                "value": _json_number(metric["decimal_value"]),
                "unit": metric.get("unit", "as_reported"),
                "source_table_id": metric.get("source_table_id"),
                "source_label": metric.get("source_label"),
            }
            for name, metric in inputs.items()
        },
        "result": _json_number(rounded_result),
        "display": (
            _display_percentage(result)
            if calculation in PERCENTAGE_CALCULATIONS
            else _display_number(result)
        ),
        "source_metric_ids": [_metric_source_id(metric) for metric in inputs.values()],
        "source_table_ids": source_table_ids,
    }


def _missing_warning(
    calculation: str,
    ticker: str,
    period: str,
    available: dict[str, dict],
    required: tuple[str, ...],
) -> dict:
    return {
        "calculation": calculation,
        "ticker": ticker,
        "period": period,
        "missing_metrics": [metric for metric in required if metric not in available],
    }


class CalculatorAgent:
    """Deterministic calculator for financial ratios and year-over-year changes."""

    def __init__(self, table_agent: TableAgent | None = None) -> None:
        self.table_agent = table_agent

    @classmethod
    def from_processed(cls, table_path: str | Path = DEFAULT_TABLE_CHUNKS_PATH) -> "CalculatorAgent":
        return cls(TableAgent.from_processed(table_path))

    def calculate_metrics(
        self,
        metrics: list[dict],
        calculations: set[str],
    ) -> tuple[list[dict], list[dict]]:
        """Calculate requested derived metrics from raw metric records."""

        grouped = _group_metrics(metrics)
        results: list[dict] = []
        warnings: list[dict] = []

        for key, available in sorted(grouped.items(), key=lambda item: (item[0][0], _period_sort_key(item[0][1]))):
            ticker, period = key
            for calculation in sorted(calculations - {"revenue_growth_yoy"}):
                required = CALCULATION_INPUTS.get(calculation)
                if not required:
                    continue
                if any(metric not in available for metric in required):
                    warnings.append(_missing_warning(calculation, ticker, period, available, required))
                    continue

                inputs = {metric: available[metric] for metric in required}
                result = self._calculate_single_period(calculation, inputs)
                if result is None:
                    warnings.append(
                        {
                            "calculation": calculation,
                            "ticker": ticker,
                            "period": period,
                            "reason": "division_by_zero",
                        }
                    )
                    continue
                results.append(_calculation_record(calculation, ticker, period, result, inputs))

        if "revenue_growth_yoy" in calculations:
            growth_results, growth_warnings = self._calculate_revenue_growth(grouped)
            results.extend(growth_results)
            warnings.extend(growth_warnings)

        results.sort(key=lambda item: (item["ticker"], item["metric"], _period_sort_key(item["period"])))
        return results, warnings

    def run(
        self,
        question: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_k: int = 5,
        calculations: set[str] | None = None,
    ) -> dict:
        """Extract table metrics and calculate requested financial metrics."""

        if self.table_agent is None:
            raise ValueError("CalculatorAgent.run requires a TableAgent. Use from_processed().")

        requested_calculations = calculations or infer_requested_calculations(question)
        metric_names = required_metrics(requested_calculations)
        table_question = question
        if "revenue_growth_yoy" in requested_calculations:
            table_question = f"{question} trend"
        table_result = self._extract_source_metrics(
            table_question,
            ticker=ticker,
            fiscal_year=fiscal_year,
            top_k=top_k,
            metrics=metric_names,
            keep_all_periods="revenue_growth_yoy" in requested_calculations,
        )
        calculation_results, warnings = self.calculate_metrics(
            table_result.get("metrics", []),
            requested_calculations,
        )

        return {
            "agent": "CalculatorAgent",
            "question": question,
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "requested_calculations": sorted(requested_calculations),
            "requested_raw_metrics": sorted(metric_names),
            "source_metric_count": len(table_result.get("metrics", [])),
            "tables_considered": table_result.get("tables_considered", []),
            "calculations": calculation_results,
            "warnings": warnings,
        }

    def _extract_source_metrics(
        self,
        question: str,
        ticker: str | None,
        fiscal_year: int | None,
        top_k: int,
        metrics: set[str],
        keep_all_periods: bool = False,
    ) -> dict:
        requested_periods = None if keep_all_periods else infer_requested_periods(question, fiscal_year)
        tables = self.table_agent.table_retriever.search(
            question,
            ticker=ticker,
            fiscal_year=fiscal_year,
            top_k=top_k,
        )

        candidates: list[dict] = []
        for table in tables:
            candidates.extend(extract_metrics_from_table(table, metrics, requested_periods))

        return {
            "metrics": candidates,
            "tables_considered": [
                {
                    "table_id": table.get("table_id"),
                    "score": round(float(table.get("score", 0.0)), 4),
                    "core_metrics": table.get("core_metrics", []),
                }
                for table in tables
            ],
        }

    def _calculate_single_period(self, calculation: str, inputs: dict[str, dict]) -> Decimal | None:
        if calculation == "gross_margin":
            return self._safe_divide(inputs["gross_profit"]["decimal_value"], inputs["revenue"]["decimal_value"])
        if calculation == "operating_margin":
            return self._safe_divide(inputs["operating_income"]["decimal_value"], inputs["revenue"]["decimal_value"])
        if calculation == "net_margin":
            return self._safe_divide(inputs["net_income"]["decimal_value"], inputs["revenue"]["decimal_value"])
        if calculation == "free_cash_flow":
            return inputs["operating_cash_flow"]["decimal_value"] - inputs["capital_expenditure"]["decimal_value"]
        if calculation == "debt_to_assets":
            return self._safe_divide(inputs["total_liabilities"]["decimal_value"], inputs["total_assets"]["decimal_value"])
        return None

    def _calculate_revenue_growth(
        self,
        grouped: dict[tuple[str, str], dict[str, dict]],
    ) -> tuple[list[dict], list[dict]]:
        results: list[dict] = []
        warnings: list[dict] = []
        by_ticker: dict[str, list[tuple[str, dict[str, dict]]]] = {}
        for (ticker, period), available in grouped.items():
            by_ticker.setdefault(ticker, []).append((period, available))

        for ticker, period_records in by_ticker.items():
            sorted_records = sorted(period_records, key=lambda item: _period_sort_key(item[0]))
            revenue_periods = [period for period, available in sorted_records if "revenue" in available]
            if len(revenue_periods) < 2:
                warnings.append(
                    {
                        "calculation": "revenue_growth_yoy",
                        "ticker": ticker,
                        "reason": "not_enough_periods",
                        "available_periods": revenue_periods,
                    }
                )
                continue

            previous_period: str | None = None
            previous_revenue: dict | None = None
            for period, available in sorted_records:
                current_revenue = available.get("revenue")
                if current_revenue is None:
                    warnings.append(
                        {
                            "calculation": "revenue_growth_yoy",
                            "ticker": ticker,
                            "period": period,
                            "missing_metrics": ["revenue"],
                        }
                    )
                    continue
                if previous_revenue is None or previous_period is None:
                    previous_period = period
                    previous_revenue = current_revenue
                    continue

                result = self._safe_divide(
                    current_revenue["decimal_value"] - previous_revenue["decimal_value"],
                    previous_revenue["decimal_value"],
                )
                if result is None:
                    warnings.append(
                        {
                            "calculation": "revenue_growth_yoy",
                            "ticker": ticker,
                            "period": period,
                            "reason": "division_by_zero",
                            "previous_period": previous_period,
                        }
                    )
                else:
                    record = _calculation_record(
                        "revenue_growth_yoy",
                        ticker,
                        period,
                        result,
                        {
                            "revenue_t": current_revenue,
                            "revenue_t_minus_1": previous_revenue,
                        },
                    )
                    record["previous_period"] = previous_period
                    results.append(record)

                previous_period = period
                previous_revenue = current_revenue

        return results, warnings

    @staticmethod
    def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal | None:
        if denominator == 0:
            return None
        return numerator / denominator


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CalculatorAgent.")
    parser.add_argument("question", help="Question to calculate financial metrics for.")
    parser.add_argument("--ticker", default=None, help="Optional ticker filter, e.g. AAPL.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year filter.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of tables to inspect.")
    parser.add_argument("--tables", default=DEFAULT_TABLE_CHUNKS_PATH, help="Path to table_chunks.jsonl.")
    args = parser.parse_args()

    agent = CalculatorAgent.from_processed(args.tables)
    result = agent.run(args.question, ticker=args.ticker, fiscal_year=args.year, top_k=args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
