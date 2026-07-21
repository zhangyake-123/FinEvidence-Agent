import unittest

from finevidence.indexing.reranker import EvidenceReranker, infer_query_type, infer_requested_metrics


class EvidenceRerankerTest(unittest.TestCase):
    def test_reranks_risk_section_above_generic_text(self) -> None:
        evidence = [
            {
                "evidence_type": "text",
                "id": "generic",
                "score": 10.0,
                "section": "Item 15. Exhibits and Financial Statement Schedules",
                "content": "This exhibit mentions competition and supply terms in passing.",
            },
            {
                "evidence_type": "text",
                "id": "risk",
                "score": 9.8,
                "section": "Item 1A. Risk Factors",
                "content": "Supply chain disruption and intense competition could harm the company.",
            },
        ]

        results = EvidenceReranker().rerank("supply chain competition risks", evidence, top_k=2)

        self.assertEqual(results[0]["id"], "risk")
        self.assertGreater(results[0]["rerank_features"]["section_bonus"], 0.0)
        self.assertEqual(results[0]["retrieval_score"], 9.8)

    def test_reranks_matching_financial_table(self) -> None:
        evidence = [
            {
                "evidence_type": "table",
                "id": "stock_table",
                "score": 3.0,
                "core_metrics": [],
                "columns": ["Shares", "2025"],
                "rows": [["Common stock", "100"]],
            },
            {
                "evidence_type": "table",
                "id": "income_table",
                "score": 2.9,
                "core_metrics": ["gross_profit", "revenue", "net_income"],
                "columns": ["Metric", "2025"],
                "rows": [["Revenue", "416161"], ["Gross margin", "195201"]],
            },
        ]

        results = EvidenceReranker().rerank("What was gross margin in 2025?", evidence, top_k=2)

        self.assertEqual(results[0]["id"], "income_table")
        self.assertIn("gross_profit", results[0]["rerank_features"]["matched_metrics"])

    def test_infers_query_type_and_metrics(self) -> None:
        self.assertEqual(infer_query_type("What are the supply chain risk factors?"), "text")
        self.assertEqual(infer_query_type("What was revenue in 2025?"), "table")
        self.assertEqual(
            infer_requested_metrics("Calculate net margin from revenue and net income"),
            {"revenue", "net_income"},
        )


if __name__ == "__main__":
    unittest.main()
