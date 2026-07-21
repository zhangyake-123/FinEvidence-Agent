import unittest

from finevidence.indexing.bm25_index import BM25Index
from finevidence.indexing.hybrid_retriever import HybridRetriever
from finevidence.indexing.table_retriever import TableRetriever


class HybridRetrieverTest(unittest.TestCase):
    def test_rerank_adds_rerank_fields(self) -> None:
        retriever = HybridRetriever(
            text_index=BM25Index(
                [
                    {
                        "chunk_id": "risk_text",
                        "ticker": "AAPL",
                        "fiscal_year": 2025,
                        "filing_type": "10-K",
                        "section": "Item 1A. Risk Factors",
                        "text": "Supply chain disruption and competition risks.",
                    }
                ]
            ),
            table_retriever=TableRetriever(
                [
                    {
                        "table_id": "income_table",
                        "ticker": "AAPL",
                        "fiscal_year": 2025,
                        "filing_type": "10-K",
                        "table_index": 1,
                        "columns": ["Metric", "2025"],
                        "rows": [["Revenue", "416161"], ["Gross margin", "195201"]],
                    }
                ]
            ),
        )

        results = retriever.retrieve(
            "What was Apple gross margin in 2025?",
            ticker="AAPL",
            fiscal_year=2025,
            top_k=1,
            rerank=True,
            candidate_k=3,
        )

        self.assertEqual(len(results), 1)
        self.assertIn("rerank_score", results[0])
        self.assertIn("retrieval_score", results[0])
        self.assertIn("rerank_features", results[0])

    def test_default_retrieval_does_not_rerank(self) -> None:
        retriever = HybridRetriever(
            text_index=BM25Index(
                [
                    {
                        "chunk_id": "risk_text",
                        "ticker": "AAPL",
                        "fiscal_year": 2025,
                        "filing_type": "10-K",
                        "section": "Item 1A. Risk Factors",
                        "text": "Supply chain disruption and competition risks.",
                    }
                ]
            ),
            table_retriever=TableRetriever([]),
        )

        results = retriever.retrieve(
            "supply chain risk",
            ticker="AAPL",
            fiscal_year=2025,
            top_k=1,
        )

        self.assertEqual(len(results), 1)
        self.assertNotIn("rerank_score", results[0])


if __name__ == "__main__":
    unittest.main()
