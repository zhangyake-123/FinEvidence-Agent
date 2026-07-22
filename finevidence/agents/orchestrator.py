"""End-to-end FinEvidence agent workflow orchestration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from finevidence.agents.planner import PlannerAgent, classify_question, infer_fact_metrics
from finevidence.agents.report_agent import ReportAgent
from finevidence.agents.retriever_agent import RetrieverAgent, summarize_evidence
from finevidence.agents.table_agent import TableAgent
from finevidence.agents.verifier_agent import VerifierAgent
from finevidence.indexing.bm25_index import DEFAULT_TEXT_CHUNKS_PATH
from finevidence.indexing.table_retriever import DEFAULT_TABLE_CHUNKS_PATH

FACT_METRIC_LABELS = {
    "revenue": "revenue",
    "gross_profit": "gross profit",
    "operating_income": "operating income",
    "net_income": "net income",
    "operating_cash_flow": "operating cash flow",
    "total_assets": "total assets",
    "total_liabilities": "total liabilities",
    "cash_and_cash_equivalents": "cash and cash equivalents",
}


def _format_value(value: object) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    return str(value)


def _preview_text(text: str, max_chars: int = 360) -> str:
    return text[:max_chars].replace("\n", " ").strip()


def _evidence_answer(question: str, question_type: str, evidence: list[dict]) -> str:
    if not evidence:
        return (
            "I could not find enough relevant evidence in the processed filings for this question. "
            "Try a more specific ticker, fiscal year, or filing section."
        )

    title = "Risk Evidence" if question_type == "risk_summary" else "Retrieved Evidence"
    lines = [
        f"## {title}",
        f"Question: {question}",
        "",
    ]

    for index, record in enumerate(evidence, start=1):
        evidence_id = record.get("id")
        ticker = record.get("ticker")
        fiscal_year = record.get("fiscal_year")
        score = round(float(record.get("score", 0.0)), 4)

        if record.get("evidence_type") == "text":
            section = record.get("section") or "unknown section"
            preview = _preview_text(record.get("content", ""))
            lines.extend(
                [
                    f"### Evidence {index}: {evidence_id}",
                    f"- Type: text",
                    f"- Company/year: {ticker} {fiscal_year}",
                    f"- Section: {section}",
                    f"- Score: {score}",
                    f"- Preview: {preview}",
                    "",
                ]
            )
        else:
            core_metrics = ", ".join(record.get("core_metrics", [])) or "not detected"
            lines.extend(
                [
                    f"### Evidence {index}: {evidence_id}",
                    f"- Type: table",
                    f"- Company/year: {ticker} {fiscal_year}",
                    f"- Core metrics: {core_metrics}",
                    f"- Score: {score}",
                    "",
                ]
            )

    lines.extend(
        [
            "## Note",
            "This is evidence retrieval only. It preserves source candidates but does not generate unsupported conclusions.",
        ]
    )
    return "\n".join(lines)


def _fact_metric_rank(metric: dict) -> tuple[float, float, float]:
    label = str(metric.get("source_label", "")).lower()
    label_bonus = 0.0
    if metric.get("metric") == "revenue":
        if label in {"revenue", "total revenue", "net sales", "total net sales"}:
            label_bonus += 10.0
        if "deferred revenue" in label or "unearned revenue" in label:
            label_bonus -= 10.0
    if label.startswith("total "):
        label_bonus += 2.0
    return (
        label_bonus,
        float(len(metric.get("source_core_metrics", []))),
        float(metric.get("source_table_score", 0.0)),
    )


def _select_fact_metrics(metrics: list[dict]) -> list[dict]:
    best: dict[tuple[str, str, str], dict] = {}
    for metric in metrics:
        key = (
            str(metric.get("ticker", "")),
            str(metric.get("period", "")),
            str(metric.get("metric", "")),
        )
        if key not in best or _fact_metric_rank(metric) > _fact_metric_rank(best[key]):
            best[key] = metric
    return sorted(best.values(), key=lambda item: (item.get("ticker", ""), item.get("period", ""), item.get("metric", "")))


def _fact_answer(question: str, fact_metrics: list[dict], table_result: dict) -> str:
    if not fact_metrics:
        requested = ", ".join(table_result.get("requested_metrics", [])) or "the requested metric"
        return (
            "## Answer\n"
            f"I could not extract {requested} from the retrieved tables for this question.\n\n"
            "## Checks\n"
            "- Status: metric_not_found\n"
            "- Try increasing --top-k or checking whether the filing contains the requested metric."
        )

    lines = ["## Answer"]
    if len(fact_metrics) == 1:
        metric = fact_metrics[0]
        ticker = metric.get("ticker") or "The company"
        period = metric.get("period")
        label = FACT_METRIC_LABELS.get(str(metric.get("metric")), str(metric.get("metric")))
        value = _format_value(metric.get("value"))
        lines.append(f"{ticker}'s {label} in {period} was {value}.")
    else:
        lines.extend(
            [
                "| Period | Metric | Value |",
                "| --- | --- | ---: |",
            ]
        )
        for metric in fact_metrics:
            label = FACT_METRIC_LABELS.get(str(metric.get("metric")), str(metric.get("metric")))
            lines.append(f"| {metric.get('period')} | {label} | {_format_value(metric.get('value'))} |")

    lines.extend(["", "## Evidence"])
    seen_tables: set[str] = set()
    for metric in fact_metrics:
        table_id = str(metric.get("source_table_id", ""))
        if table_id and table_id not in seen_tables:
            seen_tables.add(table_id)
            lines.append(f"- {table_id}")

    lines.extend(["", "## Checks"])
    for metric in fact_metrics:
        label = FACT_METRIC_LABELS.get(str(metric.get("metric")), str(metric.get("metric")))
        lines.extend(
            [
                f"- Metric: {label}",
                f"- Period: {metric.get('period')}",
                f"- Source label: {metric.get('source_label')}",
                f"- Unit: {metric.get('unit', 'as_reported')}",
            ]
        )
    return "\n".join(lines)


def _step(name: str, status: str = "completed", **details: object) -> dict:
    record = {"step": name, "status": status}
    if details:
        record["details"] = details
    return record


class FinEvidenceOrchestrator:
    """Coordinate retrieval, calculation, and report generation for MVP workflows."""

    def __init__(
        self,
        retriever_agent: RetrieverAgent,
        table_agent: TableAgent,
        report_agent: ReportAgent,
        planner_agent: PlannerAgent | None = None,
        verifier_agent: VerifierAgent | None = None,
    ) -> None:
        self.retriever_agent = retriever_agent
        self.table_agent = table_agent
        self.report_agent = report_agent
        self.planner_agent = planner_agent or PlannerAgent()
        self.verifier_agent = verifier_agent or VerifierAgent()

    @classmethod
    def from_processed(
        cls,
        text_path: str | Path = DEFAULT_TEXT_CHUNKS_PATH,
        table_path: str | Path = DEFAULT_TABLE_CHUNKS_PATH,
    ) -> "FinEvidenceOrchestrator":
        return cls(
            retriever_agent=RetrieverAgent.from_processed(text_path, table_path),
            table_agent=TableAgent.from_processed(table_path),
            report_agent=ReportAgent.from_processed(table_path),
            planner_agent=PlannerAgent(),
            verifier_agent=VerifierAgent(),
        )

    def run(
        self,
        question: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_k: int = 8,
    ) -> dict:
        """Run the first end-to-end FinEvidence workflow."""

        plan = self.planner_agent.run(
            question,
            ticker=ticker,
            fiscal_year=fiscal_year,
            top_k=top_k,
        )
        question_type = plan["question_type"]
        steps = [
            _step(
                "plan_question",
                question_type=question_type,
                requested_metrics=plan.get("requested_metrics", []),
                requested_calculations=plan.get("requested_calculations", []),
                planned_steps=plan.get("steps", []),
            )
        ]

        retrieval_result = self.retriever_agent.run(
            question,
            ticker=ticker,
            fiscal_year=fiscal_year,
            top_k=top_k,
        )
        evidence = retrieval_result.get("evidence", [])
        evidence_summary = [summarize_evidence(record) for record in evidence]
        steps.append(_step("retrieve_evidence", evidence_count=len(evidence)))

        fact_metrics = set(plan.get("requested_metrics", []))
        if question_type == "fact_qa" and fact_metrics:
            table_result = self.table_agent.run(
                question,
                ticker=ticker,
                fiscal_year=fiscal_year,
                top_k=max(top_k, 8),
                metrics=fact_metrics,
            )
            selected_metrics = _select_fact_metrics(table_result.get("metrics", []))
            answer = _fact_answer(question, selected_metrics, table_result)
            verifier_report = self.verifier_agent.run(
                answer=answer,
                facts=selected_metrics,
                evidence=evidence_summary,
            )
            claims = verifier_report["claims"]
            verification_report = verifier_report["numeric_report"]
            evidence_verification_report = verifier_report["evidence_report"]
            steps.extend(
                [
                    _step("extract_fact_metrics", metric_count=len(selected_metrics), requested_metrics=sorted(fact_metrics)),
                    _step(
                        "run_verifier_agent",
                        status=verifier_report["status"],
                        claim_count=len(claims),
                        numeric_status=verification_report["status"],
                        evidence_status=evidence_verification_report["status"],
                    ),
                    _step("render_fact_answer", format="markdown"),
                ]
            )
            return {
                "agent": "FinEvidenceOrchestrator",
                "question": question,
                "ticker": ticker,
                "fiscal_year": fiscal_year,
                "question_type": question_type,
                "plan": plan,
                "steps": steps,
                "answer": answer,
                "evidence": evidence_summary,
                "claims": claims,
                "facts": selected_metrics,
                "calculations": [],
                "verification_report": verification_report,
                "evidence_verification_report": evidence_verification_report,
                "verifier_report": verifier_report,
                "warnings": verifier_report["warnings"],
            }

        if question_type in {"metric_calc", "trend_analysis"}:
            report_result = self.report_agent.run(
                question,
                ticker=ticker,
                fiscal_year=fiscal_year,
                top_k=top_k,
            )
            calculator_result = report_result.get("calculator_result", {})
            verifier_report = self.verifier_agent.run(
                answer=report_result.get("report", ""),
                calculations=calculator_result.get("calculations", []),
                evidence=evidence_summary,
            )
            claims = verifier_report["claims"]
            verification_report = verifier_report["numeric_report"]
            evidence_verification_report = verifier_report["evidence_report"]
            warnings = calculator_result.get("warnings", []) + verifier_report["warnings"]
            steps.extend(
                [
                    _step(
                        "calculate_metrics",
                        calculation_count=len(calculator_result.get("calculations", [])),
                        warning_count=len(calculator_result.get("warnings", [])),
                    ),
                    _step(
                        "run_verifier_agent",
                        status=verifier_report["status"],
                        claim_count=len(claims),
                        numeric_status=verification_report["status"],
                        evidence_status=evidence_verification_report["status"],
                    ),
                    _step("render_report", format="markdown"),
                ]
            )
            return {
                "agent": "FinEvidenceOrchestrator",
                "question": question,
                "ticker": ticker,
                "fiscal_year": fiscal_year,
                "question_type": question_type,
                "plan": plan,
                "steps": steps,
                "answer": report_result.get("report", ""),
                "evidence": evidence_summary,
                "claims": claims,
                "calculations": calculator_result.get("calculations", []),
                "verification_report": verification_report,
                "evidence_verification_report": evidence_verification_report,
                "verifier_report": verifier_report,
                "warnings": warnings,
            }

        answer = _evidence_answer(question, question_type, evidence)
        verifier_report = self.verifier_agent.run(
            answer=answer,
            evidence=evidence_summary,
            extract_answer_claims=False,
        )
        claims = verifier_report["claims"]
        verification_report = verifier_report["numeric_report"]
        evidence_verification_report = verifier_report["evidence_report"]
        steps.extend(
            [
                _step("render_evidence_answer", format="markdown"),
                _step(
                    "run_verifier_agent",
                    status=verifier_report["status"],
                    claim_count=len(claims),
                    numeric_status=verification_report["status"],
                    evidence_status=evidence_verification_report["status"],
                ),
            ]
        )
        return {
            "agent": "FinEvidenceOrchestrator",
            "question": question,
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "question_type": question_type,
            "plan": plan,
            "steps": steps,
            "answer": answer,
            "evidence": evidence_summary,
            "claims": claims,
            "calculations": [],
            "verification_report": verification_report,
            "evidence_verification_report": evidence_verification_report,
            "verifier_report": verifier_report,
            "warnings": verifier_report["warnings"],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the end-to-end FinEvidence orchestrator.")
    parser.add_argument("question", help="Financial research question.")
    parser.add_argument("--ticker", default=None, help="Optional ticker filter, e.g. AAPL.")
    parser.add_argument("--year", type=int, default=None, help="Optional fiscal year filter.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of evidence records or tables to inspect.")
    parser.add_argument("--text-chunks", default=DEFAULT_TEXT_CHUNKS_PATH, help="Path to text_chunks.jsonl.")
    parser.add_argument("--tables", default=DEFAULT_TABLE_CHUNKS_PATH, help="Path to table_chunks.jsonl.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    orchestrator = FinEvidenceOrchestrator.from_processed(args.text_chunks, args.tables)
    result = orchestrator.run(
        args.question,
        ticker=args.ticker,
        fiscal_year=args.year,
        top_k=args.top_k,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["answer"])


if __name__ == "__main__":
    main()
