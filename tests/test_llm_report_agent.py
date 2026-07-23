import unittest

from finevidence.agents.llm_report_agent import (
    LLMReportAgent,
    build_llm_payload,
    build_trend_insights,
)


TABLE_ID = "AAPL_2025_10K_table_0014"


def gross_margin_record(period: str, display: str, result: float) -> dict:
    return {
        "metric": "gross_margin",
        "ticker": "AAPL",
        "period": period,
        "formula": "gross_profit / revenue",
        "inputs": {
            "gross_profit": {"value": 195201, "source_table_id": TABLE_ID},
            "revenue": {"value": 416161, "source_table_id": TABLE_ID},
        },
        "result": result,
        "display": display,
        "source_table_ids": [TABLE_ID],
    }


class FakeLLMClient:
    def __init__(self) -> None:
        self.payload = None
        self.schema = None

    def generate_json(self, system_prompt: str, user_payload: dict, schema: dict, schema_name: str) -> dict:
        self.payload = user_payload
        self.schema = schema
        return {
            "answer_markdown": "## Conclusion\nAAPL's gross margin improved over the period [T1].",
            "used_evidence_ids": [TABLE_ID],
            "citations": [{"marker": "T1", "evidence_id": TABLE_ID}],
            "limitations": [],
        }


class LLMReportAgentTest(unittest.TestCase):
    def test_builds_trend_insights_with_largest_interval(self) -> None:
        insights = build_trend_insights(
            [
                gross_margin_record("2023", "44.13%", 0.441311),
                gross_margin_record("2024", "46.21%", 0.462063),
                gross_margin_record("2025", "46.91%", 0.469052),
            ]
        )

        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0]["direction"], "steadily_improved")
        self.assertTrue(insights[0]["is_steady_improvement"])
        self.assertEqual(insights[0]["largest_increase_interval"]["from_period"], "2023")
        self.assertEqual(insights[0]["largest_increase_interval"]["to_period"], "2024")
        self.assertEqual(insights[0]["largest_increase_interval"]["delta_display"], "2.08 percentage points")

    def test_render_payload_normalizes_citations_and_appends_evidence_section(self) -> None:
        fake_client = FakeLLMClient()
        agent = LLMReportAgent(llm_client=fake_client)
        payload = build_llm_payload(
            question="Did Apple's gross margin improve?",
            question_type="trend_analysis",
            ticker="AAPL",
            fiscal_year=2025,
            evidence=[{"id": TABLE_ID}],
            calculations=[gross_margin_record("2025", "46.91%", 0.469052)],
        )

        result = agent.render_payload(payload)

        self.assertIn("## Evidence", result["report"])
        self.assertIn(f"- [T1] {TABLE_ID}", result["report"])
        self.assertEqual(result["citations"], [{"marker": "T1", "evidence_id": TABLE_ID}])
        self.assertIn(TABLE_ID, fake_client.payload["available_evidence_ids"])
        self.assertEqual(fake_client.schema["required"], ["answer_markdown", "used_evidence_ids", "citations", "limitations"])


if __name__ == "__main__":
    unittest.main()

