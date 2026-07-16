"""End-to-end FinEvidence agent workflow orchestration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from finevidence.agents.report_agent import ReportAgent
from finevidence.agents.retriever_agent import RetrieverAgent, summarize_evidence
from finevidence.indexing.bm25_index import DEFAULT_TEXT_CHUNKS_PATH
from finevidence.indexing.table_retriever import DEFAULT_TABLE_CHUNKS_PATH


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
}

TREND_TERMS = {
    "trend",
    "change",
    "changes",
    "past three years",
    "last three years",
    "over time",
}


def classify_question(question: str) -> str:
    """Classify a financial research question into a first-pass workflow route."""

    query = question.lower()
    if any(term in query for term in METRIC_TERMS):
        if any(term in query for term in TREND_TERMS):
            return "trend_analysis"
        return "metric_calc"
    if any(term in query for term in RISK_TERMS):
        return "risk_summary"
    return "fact_qa"


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


def _step(name: str, status: str = "completed", **details: object) -> dict:
    record = {"step": name, "status": status}
    if details:
        record["details"] = details
    return record


class FinEvidenceOrchestrator:
    """Coordinate retrieval, calculation, and report generation for MVP workflows."""

    def __init__(self, retriever_agent: RetrieverAgent, report_agent: ReportAgent) -> None:
        self.retriever_agent = retriever_agent
        self.report_agent = report_agent

    @classmethod
    def from_processed(
        cls,
        text_path: str | Path = DEFAULT_TEXT_CHUNKS_PATH,
        table_path: str | Path = DEFAULT_TABLE_CHUNKS_PATH,
    ) -> "FinEvidenceOrchestrator":
        return cls(
            retriever_agent=RetrieverAgent.from_processed(text_path, table_path),
            report_agent=ReportAgent.from_processed(table_path),
        )

    def run(
        self,
        question: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        top_k: int = 8,
    ) -> dict:
        """Run the first end-to-end FinEvidence workflow."""

        question_type = classify_question(question)
        steps = [_step("classify_question", question_type=question_type)]

        retrieval_result = self.retriever_agent.run(
            question,
            ticker=ticker,
            fiscal_year=fiscal_year,
            top_k=top_k,
        )
        evidence = retrieval_result.get("evidence", [])
        evidence_summary = [summarize_evidence(record) for record in evidence]
        steps.append(_step("retrieve_evidence", evidence_count=len(evidence)))

        if question_type in {"metric_calc", "trend_analysis"}:
            report_result = self.report_agent.run(
                question,
                ticker=ticker,
                fiscal_year=fiscal_year,
                top_k=top_k,
            )
            calculator_result = report_result.get("calculator_result", {})
            steps.extend(
                [
                    _step(
                        "calculate_metrics",
                        calculation_count=len(calculator_result.get("calculations", [])),
                        warning_count=len(calculator_result.get("warnings", [])),
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
                "steps": steps,
                "answer": report_result.get("report", ""),
                "evidence": evidence_summary,
                "calculations": calculator_result.get("calculations", []),
                "warnings": calculator_result.get("warnings", []),
            }

        answer = _evidence_answer(question, question_type, evidence)
        steps.append(_step("render_evidence_answer", format="markdown"))
        return {
            "agent": "FinEvidenceOrchestrator",
            "question": question,
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "question_type": question_type,
            "steps": steps,
            "answer": answer,
            "evidence": evidence_summary,
            "calculations": [],
            "warnings": [],
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
