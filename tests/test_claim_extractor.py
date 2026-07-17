import unittest

from finevidence.verification.claim_extractor import extract_claims


def gross_margin_record(period: str, display: str, result: float) -> dict:
    return {
        "metric": "gross_margin",
        "ticker": "AAPL",
        "period": period,
        "formula": "gross_profit / revenue",
        "result": result,
        "display": display,
        "source_table_ids": ["AAPL_2025_10K_table_0014"],
    }


class ClaimExtractorTest(unittest.TestCase):
    def test_extracts_numeric_and_trend_claims_from_calculations(self) -> None:
        claims = extract_claims(
            calculations=[
                gross_margin_record("2023", "44.13%", 0.441311),
                gross_margin_record("2024", "46.21%", 0.462063),
                gross_margin_record("2025", "46.91%", 0.469052),
            ]
        )

        claim_types = [claim["claim_type"] for claim in claims]
        self.assertEqual(claim_types.count("numeric_claim"), 3)
        self.assertEqual(claim_types.count("trend_claim"), 1)
        trend_claim = [claim for claim in claims if claim["claim_type"] == "trend_claim"][0]
        self.assertEqual(trend_claim["trend"], "increased")
        self.assertEqual(trend_claim["periods"], ["2023", "2024", "2025"])

    def test_extracts_fact_numeric_claim(self) -> None:
        claims = extract_claims(
            facts=[
                {
                    "ticker": "MSFT",
                    "period": "2025",
                    "metric": "net_income",
                    "value": 101832,
                    "source_table_id": "MSFT_2025_10K_table_0013",
                    "source_label": "net income",
                }
            ]
        )

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["claim_type"], "numeric_claim")
        self.assertEqual(claims[0]["source"], "fact")
        self.assertIn("101,832", claims[0]["claim"])


if __name__ == "__main__":
    unittest.main()
