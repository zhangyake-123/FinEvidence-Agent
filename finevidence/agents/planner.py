"""Planning agent for FinEvidence workflow routing."""

from __future__ import annotations

import argparse
import json

from finevidence.agents.calculator_agent import infer_requested_calculations, required_metrics
from finevidence.agents.table_agent import infer_requested_periods


METRIC_TERMS = {
    "gross margin",
    "operating margin",
    "net margin",
    "revenue growth",
    "sales growth",
    "year over year",
    "yoy",
    "free cash flow",
    "debt to assets",
    "liabilities to assets",
    "毛利率",
    "净利率",
    "经营利润率",
    "收入增长",
}

RISK_TERMS = {
    "risk",
    "risks",
    "risk factor",
    "risk factors",
    "supply chain",
    "competition",
    "competitive",
    "regulation",
    "regulatory",
    "legal",
    "风险",
    "竞争",
    "供应链",
}

TREND_TERMS = {
    "trend",
    "change",
    "changes",
    "past three years",
    "last three years",
    "over time",
    "过去",
    "三年",
    "趋势",
    "变化",
}

FACT_METRIC_TERMS = {
    "revenue": {
        "revenue",
        "revenues",
        "net sales",
        "sales",
        "收入",
    },
    "gross_profit": {
        "gross profit",
        "gross margin dollars",
        "毛利",
    },
    "operating_income": {
        "operating income",
        "经营利润",
    },
    "net_income": {
        "net income",
        "net earnings",
        "净利润",
    },
    "operating_cash_flow": {
        "operating cash flow",
        "cash flow from operations",
        "cash provided by operating activities",
        "net cash provided by operating activities",
        "经营现金流",
    },
    "total_assets": {
        "total assets",
        "assets",
        "资产",
    },
    "total_liabilities": {
        "total liabilities",
        "liabilities",
        "负债",
    },
    "cash_and_cash_equivalents": {
        "cash and cash equivalents",
        "cash equivalents",
        "现金及现金等价物",
    },
}


def classify_question(question: str) -> str:
    """Classify a financial research question into a workflow route."""

    query = question.lower()
    if any(term in query for term in METRIC_TERMS):
        if any(term in query for term in TREND_TERMS):
            return "trend_analysis"
        return "metric_calc"
    if any(term in query for term in RISK_TERMS):
        return "risk_summary"
    return "fact_qa"


def infer_fact_metrics(question: str) -> set[str]:
    """Infer raw financial metrics for fact-style numeric questions."""

    query = question.lower()
    metrics: set[str] = set()
    for metric, terms in FACT_METRIC_TERMS.items():
        if any(term in query for term in terms):
            metrics.add(metric)
    return metrics


def _planned_steps(
    question_type: str,
    requested_metrics: set[str],
    requested_calculations: set[str],
) -> list[str]:
    steps = ["retrieve_evidence"]
    if question_type == "fact_qa" and requested_metrics:
        steps.extend(["extract_fact_metrics", "verify_answer", "render_fact_answer"])
    elif question_type in {"metric_calc", "trend_analysis"}:
        steps.extend(["extract_table_metrics", "calculate_metrics", "verify_answer", "render_report"])
    elif question_type == "risk_summary":
        steps.extend(["rank_text_evidence", "verify_answer", "render_evidence_answer"])
    else:
        steps.extend(["verify_answer", "render_evidence_answer"])

    if requested_calculations and "calculate_metrics" not in steps:
        steps.insert(-2, "calculate_metrics")
    return steps


def _answer_strategy(question_type: str) -> str:
    if question_type == "fact_qa":
        return "fact_answer"
    if question_type in {"metric_calc", "trend_analysis"}:
        return "calculation_report"
    if question_type == "risk_summary":
        return "evidence_summary"
    return "evidence_summary"


class PlannerAgent:
    """Rule-based planner that prepares a structured workflow plan."""

    def run(
        self,
        question: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_k: int = 8,
    ) -> dict:
        question_type = classify_question(question)
        requested_calculations = (
            infer_requested_calculations(question)
            if question_type in {"metric_calc", "trend_analysis"}
            else set()
        )
        if question_type in {"metric_calc", "trend_analysis"}:
            requested_metrics = required_metrics(requested_calculations)
        elif question_type == "fact_qa":
            requested_metrics = infer_fact_metrics(question)
        else:
            requested_metrics = set()

        requested_periods = infer_requested_periods(question, fiscal_year=fiscal_year)
        steps = _planned_steps(question_type, requested_metrics, requested_calculations)

        return {
            "agent": "PlannerAgent",
            "question": question,
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "top_k": top_k,
            "question_type": question_type,
            "answer_strategy": _answer_strategy(question_type),
            "requested_metrics": sorted(requested_metrics),
            "requested_calculations": sorted(requested_calculations),
            "requested_periods": None if requested_periods is None else sorted(requested_periods),
            "requires_retrieval": True,
            "requires_tables": bool(requested_metrics or requested_calculations),
            "requires_calculation": bool(requested_calculations),
            "requires_verification": True,
            "steps": steps,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan a FinEvidence agent workflow.")
    parser.add_argument("question", help="Financial research question.")
    parser.add_argument("--ticker", default=None, help="Optional ticker filter, e.g. AAPL.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of evidence records to retrieve.")
    args = parser.parse_args()

    plan = PlannerAgent().run(
        args.question,
        ticker=args.ticker,
        fiscal_year=args.year,
        top_k=args.top_k,
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
