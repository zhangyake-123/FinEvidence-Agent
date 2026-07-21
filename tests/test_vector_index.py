import unittest

from finevidence.indexing.vector_index import VectorIndex


class VectorIndexTest(unittest.TestCase):
    def test_search_ranks_similar_text_first(self) -> None:
        index = VectorIndex(
            [
                {
                    "chunk_id": "risk_1",
                    "ticker": "AAPL",
                    "fiscal_year": 2025,
                    "section": "Item 1A. Risk Factors",
                    "text": "Supply chain disruption and intense competition could affect operations.",
                },
                {
                    "chunk_id": "business_1",
                    "ticker": "AAPL",
                    "fiscal_year": 2025,
                    "section": "Item 1. Business",
                    "text": "The company sells products and services through online stores.",
                },
            ]
        )

        results = index.search("supply chain competition risk", ticker="AAPL", fiscal_year=2025, top_k=1)

        self.assertEqual(results[0]["chunk_id"], "risk_1")
        self.assertGreater(results[0]["score"], 0.0)

    def test_search_filters_metadata(self) -> None:
        index = VectorIndex(
            [
                {
                    "chunk_id": "aapl_risk",
                    "ticker": "AAPL",
                    "fiscal_year": 2025,
                    "section": "Item 1A. Risk Factors",
                    "text": "Supply chain risk.",
                },
                {
                    "chunk_id": "msft_risk",
                    "ticker": "MSFT",
                    "fiscal_year": 2025,
                    "section": "Item 1A. Risk Factors",
                    "text": "Supply chain risk.",
                },
            ]
        )

        results = index.search("supply chain", ticker="MSFT", fiscal_year=2025, section="Item 1A", top_k=5)

        self.assertEqual([record["chunk_id"] for record in results], ["msft_risk"])


if __name__ == "__main__":
    unittest.main()
