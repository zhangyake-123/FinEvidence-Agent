import unittest
from typing import Optional

from finevidence.agents.orchestrator import FinEvidenceOrchestrator
from finevidence.agents.verifier_agent import VerifierAgent


TABLE_ID = "AAPL_2025_10K_table_0014"


def gross_margin_record() -> dict:
    return {
        "metric": "gross_margin",
        "ticker": "AAPL",
        "period": "2025",
        "formula": "gross_profit / revenue",
        "inputs": {
            "gross_profit": {"value": 195201, "source_table_id": TABLE_ID},
            "revenue": {"value": 416161, "source_table_id": TABLE_ID},
        },
        "result": 0.469052,
        "display": "46.91%",
        "source_table_ids": [TABLE_ID],
    }


class FakePlannerAgent:
    def run(self, question: str, ticker: Optional[str] = None, fiscal_year: Optional[int] = None, top_k: int = 8) -> dict:
        return {
            "agent": "PlannerAgent",
            "question": question,
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "top_k": top_k,
            "question_type": "metric_calc",
            "requested_metrics": ["gross_profit", "revenue"],
            "requested_calculations": ["gross_margin"],
            "steps": ["retrieve_evidence", "calculate_metrics", "verify_answer", "render_report"],
        }


class FakeRetrieverAgent:
    def run(self, question: str, ticker: Optional[str] = None, fiscal_year: Optional[int] = None, top_k: int = 8) -> dict:
        return {
            "evidence": [
                {
                    "evidence_type": "table",
                    "id": TABLE_ID,
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "source_path": "fake.html",
                    "score": 10.0,
                    "table_index": 14,
                    "core_metrics": ["revenue", "gross_profit"],
                    "rows": [],
                }
            ]
        }


class FakeTableAgent:
    pass


class FakeReportAgent:
    def run(self, question: str, ticker: Optional[str] = None, fiscal_year: Optional[int] = None, top_k: int = 5) -> dict:
        return {
            "calculator_result": {
                "calculations": [gross_margin_record()],
                "warnings": [],
            },
            "report": f"## Conclusion\nAAPL's gross margin was 46.91% [T1].\n\n## Evidence\n- [T1] {TABLE_ID}",
        }


class FakeLLMReportAgent:
    def __init__(self) -> None:
        self.payload = None

    def render_payload(self, payload: dict) -> dict:
        self.payload = payload
        return {
            "agent": "LLMReportAgent",
            "report": f"## Conclusion\nAAPL's gross margin was 46.91% [T1].\n\n## Evidence\n- [T1] {TABLE_ID}",
            "citations": [{"marker": "T1", "evidence_id": TABLE_ID}],
            "used_evidence_ids": [TABLE_ID],
            "limitations": [],
        }


class OrchestratorLLMReportModeTest(unittest.TestCase):
    def test_llm_report_mode_uses_llm_report_agent(self) -> None:
        fake_llm = FakeLLMReportAgent()
        orchestrator = FinEvidenceOrchestrator(
            retriever_agent=FakeRetrieverAgent(),
            table_agent=FakeTableAgent(),
            report_agent=FakeReportAgent(),
            planner_agent=FakePlannerAgent(),
            verifier_agent=VerifierAgent(),
            llm_report_agent=fake_llm,
        )

        result = orchestrator.run(
            "What was Apple gross margin in 2025?",
            ticker="AAPL",
            fiscal_year=2025,
            top_k=5,
            report_mode="llm",
        )

        self.assertEqual(result["report_mode"], "llm")
        self.assertEqual(result["verifier_report"]["status"], "passed")
        self.assertIsNotNone(result["llm_report_result"])
        self.assertEqual(fake_llm.payload["question_type"], "metric_calc")
        self.assertIn(TABLE_ID, fake_llm.payload["available_evidence_ids"])


if __name__ == "__main__":
    unittest.main()
