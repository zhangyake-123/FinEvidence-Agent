import unittest

from finevidence.evaluation.ablation import SUPPORTED_MODES, compact_result, run_ablation, summary_result


class AblationTest(unittest.TestCase):
    def test_text_only_ablation_runs_on_smoke_dataset(self) -> None:
        result = run_ablation(
            dataset_path="data/eval/qa_smoke.jsonl",
            modes=["text_only"],
            top_k=2,
        )

        self.assertEqual(result["modes"], ["text_only"])
        self.assertEqual(result["summary_by_mode"]["text_only"]["count"], 11)
        self.assertEqual(len(result["records_by_mode"]["text_only"]), 11)

    def test_vector_and_reranked_ablation_modes_run(self) -> None:
        result = run_ablation(
            dataset_path="data/eval/qa_smoke.jsonl",
            modes=["vector_text", "hybrid_reranked"],
            top_k=2,
        )

        self.assertEqual(result["summary_by_mode"]["vector_text"]["count"], 11)
        self.assertEqual(result["summary_by_mode"]["hybrid_reranked"]["count"], 11)

    def test_compact_result_keeps_evaluation_fields(self) -> None:
        result = run_ablation(
            dataset_path="data/eval/qa_smoke.jsonl",
            modes=["text_only"],
            top_k=1,
        )

        compact = compact_result(result)
        first_record = compact["records_by_mode"]["text_only"][0]

        self.assertIn("answer_accuracy", first_record)
        self.assertNotIn("prediction", first_record)

    def test_summary_result_omits_records(self) -> None:
        result = run_ablation(
            dataset_path="data/eval/qa_smoke.jsonl",
            modes=["text_only"],
            top_k=1,
        )

        summary = summary_result(result)

        self.assertIn("summary_by_mode", summary)
        self.assertNotIn("records_by_mode", summary)

    def test_unknown_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            run_ablation(
                dataset_path="data/eval/qa_smoke.jsonl",
                modes=["unknown_mode"],
            )

    def test_llm_report_mode_is_supported_but_not_default(self) -> None:
        self.assertIn("full_agent_llm_report", SUPPORTED_MODES)

        result = run_ablation(
            dataset_path="data/eval/qa_smoke.jsonl",
            modes=None,
            top_k=1,
        )

        self.assertNotIn("full_agent_llm_report", result["modes"])


if __name__ == "__main__":
    unittest.main()
