import unittest

from finevidence.evaluation.ablation import compact_result, run_ablation


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

    def test_unknown_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            run_ablation(
                dataset_path="data/eval/qa_smoke.jsonl",
                modes=["unknown_mode"],
            )


if __name__ == "__main__":
    unittest.main()
