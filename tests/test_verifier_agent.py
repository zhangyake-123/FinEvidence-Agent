import unittest

from finevidence.agents.verifier_agent import VerifierAgent, verify_payload


def gross_margin_record(display: str = "46.91%") -> dict:
    return {
        "metric": "gross_margin",
        "ticker": "AAPL",
        "period": "2025",
        "formula": "gross_profit / revenue",
        "inputs": {
            "gross_profit": {
                "value": 195201,
                "source_table_id": "AAPL_2025_10K_table_0014",
            },
            "revenue": {
                "value": 416161,
                "source_table_id": "AAPL_2025_10K_table_0014",
            },
        },
        "result": 0.469052,
        "display": display,
        "source_table_ids": ["AAPL_2025_10K_table_0014"],
    }


def net_income_fact() -> dict:
    return {
        "ticker": "MSFT",
        "period": "2025",
        "metric": "net_income",
        "value": 101832,
        "source_table_id": "MSFT_2025_10K_table_0013",
        "source_label": "net income",
    }


class VerifierAgentTest(unittest.TestCase):
    def test_calculation_answer_passes_numeric_and_evidence_checks(self) -> None:
        report = VerifierAgent().run(
            answer="AAPL's gross margin was 46.91% in 2025.",
            calculations=[gross_margin_record()],
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["claim_count"], 1)
        self.assertEqual(report["numeric_report"]["status"], "passed")
        self.assertEqual(report["evidence_report"]["status"], "supported")
        self.assertEqual(report["citation_report"]["status"], "not_applicable")

    def test_numeric_error_fails_overall_verification(self) -> None:
        report = VerifierAgent().run(
            answer="AAPL's gross margin was 4.69% in 2025.",
            calculations=[gross_margin_record(display="4.69%")],
        )

        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["numeric_report"]["status"], "numeric_error")
        self.assertTrue(report["warnings"])

    def test_fact_answer_passes(self) -> None:
        fact = net_income_fact()
        report = VerifierAgent().run(
            answer="MSFT's net income in 2025 was 101,832.",
            facts=[fact],
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["claim_count"], 1)
        self.assertEqual(report["claims"][0]["source"], "fact")

    def test_retrieval_only_answer_can_skip_claim_extraction(self) -> None:
        report = VerifierAgent().run(
            answer="Evidence 1 score: 21.0187.",
            evidence=[{"id": "AAPL_2025_10K_item_1a_risk_factors_0001"}],
            extract_answer_claims=False,
        )

        self.assertEqual(report["status"], "not_applicable")
        self.assertEqual(report["claim_count"], 0)
        self.assertEqual(report["claims"], [])

    def test_verify_payload_uses_existing_claims_when_supplied(self) -> None:
        report = verify_payload(
            {
                "answer": "AAPL's gross margin was 46.91% in 2025.",
                "calculations": [gross_margin_record()],
                "claims": [
                    {
                        "claim_id": "manual_0001",
                        "claim_type": "numeric_claim",
                        "claim": "AAPL's gross margin was 46.91% in 2025.",
                        "source": "calculation",
                        "ticker": "AAPL",
                        "metric": "gross_margin",
                        "period": "2025",
                        "value": 0.469052,
                        "display": "46.91%",
                        "source_table_ids": ["AAPL_2025_10K_table_0014"],
                    }
                ],
            }
        )

        self.assertEqual(report["claims"][0]["claim_id"], "manual_0001")
        self.assertEqual(report["status"], "passed")

    def test_required_citation_can_fail_overall_verification(self) -> None:
        report = VerifierAgent().run(
            answer="AAPL's gross margin was 46.91% in 2025.",
            calculations=[gross_margin_record()],
            require_citations=True,
        )

        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["citation_report"]["status"], "missing_citation")

    def test_required_citation_passes_when_source_is_cited(self) -> None:
        report = VerifierAgent().run(
            answer=(
                "AAPL's gross margin was 46.91% in 2025 [T1].\n\n"
                "## Evidence\n"
                "- [T1] AAPL_2025_10K_table_0014"
            ),
            calculations=[gross_margin_record()],
            require_citations=True,
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["citation_report"]["status"], "passed")


if __name__ == "__main__":
    unittest.main()
