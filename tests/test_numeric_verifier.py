import unittest

from finevidence.verification.numeric_verifier import verify_calculation, verify_numeric_outputs


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


class NumericVerifierTest(unittest.TestCase):
    def test_valid_gross_margin_passes(self) -> None:
        report = verify_calculation(gross_margin_record())

        self.assertEqual(report["status"], "passed")

    def test_bad_percentage_display_is_numeric_error(self) -> None:
        report = verify_calculation(gross_margin_record(display="4.69%"))

        self.assertEqual(report["status"], "numeric_error")
        display_checks = [check for check in report["checks"] if check["check"] == "display"]
        self.assertEqual(display_checks[0]["status"], "numeric_error")

    def test_fact_answer_must_contain_metric_value(self) -> None:
        fact = {
            "ticker": "MSFT",
            "period": "2025",
            "metric": "net_income",
            "value": 101832,
            "source_table_id": "MSFT_2025_10K_table_0013",
            "source_label": "net income",
        }

        report = verify_numeric_outputs(facts=[fact], answer="MSFT's net income in 2025 was 101,832.")

        self.assertEqual(report["status"], "passed")


if __name__ == "__main__":
    unittest.main()
