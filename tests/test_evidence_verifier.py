import unittest

from finevidence.verification.claim_extractor import extract_claims
from finevidence.verification.evidence_verifier import verify_evidence_support


def gross_margin_record(period: str, display: str, result: float) -> dict:
    return {
        "metric": "gross_margin",
        "ticker": "AAPL",
        "period": period,
        "formula": "gross_profit / revenue",
        "result": result,
        "display": display,
        "source_table_ids": [f"AAPL_{period}_10K_table_0014"],
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


class EvidenceVerifierTest(unittest.TestCase):
    def test_numeric_calculation_claim_is_supported(self) -> None:
        calculations = [gross_margin_record("2025", "46.91%", 0.469052)]
        claims = extract_claims(calculations=calculations)

        report = verify_evidence_support(claims=claims, calculations=calculations)

        self.assertEqual(report["status"], "supported")
        self.assertEqual(report["supported_count"], 1)

    def test_trend_claim_is_supported_by_period_calculations(self) -> None:
        calculations = [
            gross_margin_record("2023", "44.13%", 0.441311),
            gross_margin_record("2024", "46.21%", 0.462063),
            gross_margin_record("2025", "46.91%", 0.469052),
        ]
        claims = extract_claims(calculations=calculations)

        report = verify_evidence_support(claims=claims, calculations=calculations)

        trend_checks = [check for check in report["claim_checks"] if check["claim_type"] == "trend_claim"]
        self.assertEqual(report["status"], "supported")
        self.assertEqual(trend_checks[0]["status"], "supported")
        self.assertEqual(len(trend_checks[0]["evidence_ids"]), 3)

    def test_fact_claim_is_supported(self) -> None:
        facts = [net_income_fact()]
        claims = extract_claims(facts=facts)

        report = verify_evidence_support(claims=claims, facts=facts)

        self.assertEqual(report["status"], "supported")
        self.assertEqual(report["claim_checks"][0]["evidence_ids"], ["MSFT_2025_10K_table_0013"])

    def test_missing_calculation_is_unsupported(self) -> None:
        claim = extract_claims(calculations=[gross_margin_record("2025", "46.91%", 0.469052)])[0]

        report = verify_evidence_support(claims=[claim], calculations=[])

        self.assertEqual(report["status"], "unsupported")
        self.assertEqual(report["claim_checks"][0]["reason"], "no_matching_calculation_record")


if __name__ == "__main__":
    unittest.main()
