import unittest

from finevidence.evaluation.dataset import load_eval_dataset
from finevidence.evaluation.metrics import evaluate_prediction, summarize_results


class EvaluationTest(unittest.TestCase):
    def test_load_eval_dataset(self) -> None:
        examples = load_eval_dataset("data/eval/qa_smoke.jsonl")

        self.assertGreaterEqual(len(examples), 10)
        self.assertEqual(examples[0]["id"], "smoke_001")
        self.assertIn("question", examples[0])

    def test_evaluate_prediction_scores_numbers_and_evidence(self) -> None:
        example = {
            "id": "qa_test",
            "ticker": "AAPL",
            "question_type": "metric_calc",
            "gold_numbers": [{"metric": "gross_margin", "period": "2025", "value": 0.469052}],
            "gold_evidence_ids": ["AAPL_2025_10K_table_0014"],
            "gold_answer_contains": ["46.91%"],
        }
        prediction = {
            "answer": "AAPL's gross margin was 46.91% in 2025.",
            "evidence": [{"id": "AAPL_2025_10K_table_0014"}],
            "calculations": [
                {
                    "metric": "gross_margin",
                    "period": "2025",
                    "result": 0.469052,
                    "source_table_ids": ["AAPL_2025_10K_table_0014"],
                }
            ],
            "verifier_report": {
                "status": "passed",
                "numeric_report": {"status": "passed"},
                "evidence_report": {"status": "supported", "claim_checks": []},
                "citation_report": {"status": "passed"},
            },
            "steps": [{"step": "run_verifier_agent", "status": "passed"}],
        }

        record = evaluate_prediction(example, prediction)

        self.assertEqual(record["answer_accuracy"], 1.0)
        self.assertEqual(record["evidence_recall"], 1.0)
        self.assertEqual(record["numeric_consistency"], 1.0)
        self.assertEqual(record["hallucination_free"], 1.0)
        self.assertEqual(record["citation_accuracy"], 1.0)
        self.assertEqual(record["tool_success"], 1.0)

    def test_summarize_results(self) -> None:
        summary = summarize_results(
            [
                {
                    "answer_accuracy": 1.0,
                    "evidence_recall": 1.0,
                    "numeric_consistency": 1.0,
                    "hallucination_free": 1.0,
                    "citation_accuracy": 1.0,
                    "tool_success": 1.0,
                    "numeric_status": "passed",
                    "evidence_status": "supported",
                    "citation_status": "passed",
                },
                {
                    "answer_accuracy": 0.0,
                    "evidence_recall": 0.0,
                    "numeric_consistency": 0.0,
                    "hallucination_free": 0.0,
                    "citation_accuracy": 0.0,
                    "tool_success": 1.0,
                    "numeric_status": "numeric_error",
                    "evidence_status": "unsupported",
                    "citation_status": "missing_citation",
                },
            ]
        )

        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["answer_accuracy"], 0.5)
        self.assertEqual(summary["citation_accuracy"], 0.5)
        self.assertEqual(summary["hallucination_rate"], 0.5)
        self.assertEqual(summary["tool_success_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
