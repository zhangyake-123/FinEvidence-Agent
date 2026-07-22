import unittest

from finevidence.verification.citation_checker import (
    available_evidence_ids,
    check_citations,
    extract_citations,
)


TABLE_ID = "AAPL_2025_10K_table_0014"
TEXT_ID = "AAPL_2025_10K_item_1a_risk_factors_0001"


def gross_margin_record() -> dict:
    return {
        "metric": "gross_margin",
        "ticker": "AAPL",
        "period": "2025",
        "source_table_ids": [TABLE_ID],
        "inputs": {
            "gross_profit": {"value": 195201, "source_table_id": TABLE_ID},
            "revenue": {"value": 416161, "source_table_id": TABLE_ID},
        },
    }


class CitationCheckerTest(unittest.TestCase):
    def test_extracts_alias_and_direct_evidence_ids(self) -> None:
        answer = f"Gross margin was 46.91% [T1].\n\n## Evidence\n- [T1] {TABLE_ID}"

        extracted = extract_citations(answer)

        self.assertEqual(extracted["alias_citations"], ["T1"])
        self.assertEqual(extracted["citation_map"], {"T1": TABLE_ID})
        self.assertEqual(extracted["direct_evidence_ids"], [TABLE_ID])
        self.assertEqual(extracted["cited_evidence_ids"], [TABLE_ID])

    def test_passes_when_required_source_is_cited(self) -> None:
        answer = f"Gross margin was 46.91% [T1].\n\n## Evidence\n- [T1] {TABLE_ID}"

        report = check_citations(
            answer=answer,
            calculations=[gross_margin_record()],
            require_citations=True,
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["missing_required_evidence_ids"], [])

    def test_fails_when_required_source_is_missing(self) -> None:
        report = check_citations(
            answer="Gross margin was 46.91%.",
            calculations=[gross_margin_record()],
            require_citations=True,
        )

        self.assertEqual(report["status"], "missing_citation")
        self.assertEqual(report["missing_required_evidence_ids"], [TABLE_ID])

    def test_fails_unknown_alias(self) -> None:
        report = check_citations(
            answer="Gross margin was 46.91% [T2].",
            calculations=[gross_margin_record()],
        )

        self.assertEqual(report["status"], "unknown_citation")
        self.assertEqual(report["unknown_aliases"], ["T2"])

    def test_direct_text_evidence_id_passes(self) -> None:
        report = check_citations(
            answer=f"Evidence 1: {TEXT_ID}",
            evidence=[{"id": TEXT_ID}],
            require_citations=True,
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["direct_evidence_ids"], [TEXT_ID])

    def test_retrieval_answer_needs_at_least_one_citation_when_required(self) -> None:
        report = check_citations(
            answer="The risk factors discuss supply constraints.",
            evidence=[{"id": TEXT_ID}],
            require_citations=True,
        )

        self.assertEqual(report["status"], "missing_citation")
        self.assertEqual(report["issues"][0]["type"], "missing_retrieved_evidence")

    def test_available_evidence_collects_structured_sources(self) -> None:
        ids = available_evidence_ids(
            evidence=[{"id": TEXT_ID}],
            calculations=[gross_margin_record()],
        )

        self.assertEqual(ids, [TEXT_ID, TABLE_ID])


if __name__ == "__main__":
    unittest.main()
