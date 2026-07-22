"""Rule-based citation checker for evidence-backed answers."""

from __future__ import annotations

import argparse
import json
import re


EVIDENCE_ID_PATTERN = r"[A-Z]{1,8}_20\d{2}_10K_(?:table_\d{4}|item_[a-z0-9_]+_\d{4})"
EVIDENCE_ID_RE = re.compile(rf"\b({EVIDENCE_ID_PATTERN})\b", re.IGNORECASE)
CITATION_RE = re.compile(r"\[([A-Za-z]+\d+)\]")
CITATION_MAP_RE = re.compile(
    rf"\[([A-Za-z]+\d+)\]\s+({EVIDENCE_ID_PATTERN})\b",
    re.IGNORECASE,
)


def _evidence_id(record: dict) -> str:
    for field in ("id", "source_table_id", "table_id", "chunk_id"):
        if record.get(field):
            return str(record[field])
    return ""


def _source_table_ids(record: dict) -> list[str]:
    ids = [str(table_id) for table_id in record.get("source_table_ids", []) if table_id]
    if record.get("source_table_id"):
        ids.append(str(record["source_table_id"]))

    inputs = record.get("inputs", {})
    if isinstance(inputs, dict):
        for metric in inputs.values():
            if isinstance(metric, dict) and metric.get("source_table_id"):
                ids.append(str(metric["source_table_id"]))
    return _unique(ids)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            unique_values.append(value)
    return unique_values


def _sorted_ids(values: set[str] | list[str]) -> list[str]:
    return sorted(values, key=lambda value: value.lower())


def extract_citation_map(answer: str | None) -> dict[str, str]:
    """Extract mappings such as ``[T1] AAPL_2025_10K_table_0014`` from an answer."""

    if not answer:
        return {}

    citation_map: dict[str, str] = {}
    for alias, evidence_id in CITATION_MAP_RE.findall(answer):
        citation_map[alias.upper()] = evidence_id
    return citation_map


def extract_citations(answer: str | None) -> dict:
    """Extract bracket citations and direct SEC evidence ids from answer text."""

    answer = answer or ""
    alias_citations = [alias.upper() for alias in CITATION_RE.findall(answer)]
    direct_evidence_ids = EVIDENCE_ID_RE.findall(answer)
    citation_map = extract_citation_map(answer)

    mapped_evidence_ids = [
        citation_map[alias]
        for alias in alias_citations
        if alias in citation_map
    ]
    cited_evidence_ids = _unique(mapped_evidence_ids + direct_evidence_ids)

    return {
        "alias_citations": _unique(alias_citations),
        "direct_evidence_ids": _unique(direct_evidence_ids),
        "citation_map": citation_map,
        "cited_evidence_ids": cited_evidence_ids,
    }


def available_evidence_ids(
    evidence: list[dict] | None = None,
    calculations: list[dict] | None = None,
    facts: list[dict] | None = None,
    claims: list[dict] | None = None,
) -> list[str]:
    """Collect evidence ids that the current workflow actually made available."""

    ids: list[str] = []
    for record in evidence or []:
        evidence_id = _evidence_id(record)
        if evidence_id:
            ids.append(evidence_id)

    for record in calculations or []:
        ids.extend(_source_table_ids(record))

    for record in facts or []:
        ids.extend(_source_table_ids(record))

    for record in claims or []:
        ids.extend(_source_table_ids(record))

    return _unique(ids)


def required_evidence_ids(
    calculations: list[dict] | None = None,
    facts: list[dict] | None = None,
    claims: list[dict] | None = None,
) -> list[str]:
    """Collect ids that should be cited for structured facts or calculations."""

    ids: list[str] = []
    for record in calculations or []:
        ids.extend(_source_table_ids(record))
    for record in facts or []:
        ids.extend(_source_table_ids(record))
    for record in claims or []:
        if record.get("source") in {"calculation", "fact"}:
            ids.extend(_source_table_ids(record))
    return _unique(ids)


def _issue(issue_type: str, message: str, values: list[str]) -> dict:
    return {
        "type": issue_type,
        "message": message,
        "values": values,
    }


def _status(issues: list[dict], extracted: dict) -> str:
    if any(issue["type"] == "unknown_alias" for issue in issues):
        return "unknown_citation"
    if any(issue["type"] == "unknown_evidence_id" for issue in issues):
        return "unknown_citation"
    if any(issue["type"].startswith("missing_") for issue in issues):
        return "missing_citation"
    if extracted["alias_citations"] or extracted["direct_evidence_ids"]:
        return "passed"
    return "not_applicable"


def check_citations(
    answer: str | None = None,
    evidence: list[dict] | None = None,
    calculations: list[dict] | None = None,
    facts: list[dict] | None = None,
    claims: list[dict] | None = None,
    require_citations: bool = False,
) -> dict:
    """Check whether answer citations point to available evidence ids."""

    extracted = extract_citations(answer)
    available_ids = available_evidence_ids(
        evidence=evidence,
        calculations=calculations,
        facts=facts,
        claims=claims,
    )
    required_ids = required_evidence_ids(
        calculations=calculations,
        facts=facts,
        claims=claims,
    )

    available_by_key = {evidence_id.lower(): evidence_id for evidence_id in available_ids}
    cited_by_key = {evidence_id.lower(): evidence_id for evidence_id in extracted["cited_evidence_ids"]}
    required_by_key = {evidence_id.lower(): evidence_id for evidence_id in required_ids}

    unknown_aliases = [
        alias
        for alias in extracted["alias_citations"]
        if alias not in extracted["citation_map"]
    ]
    unknown_evidence_ids = [
        evidence_id
        for key, evidence_id in cited_by_key.items()
        if key not in available_by_key
    ]
    missing_required_ids = [
        evidence_id
        for key, evidence_id in required_by_key.items()
        if key not in cited_by_key
    ]

    issues: list[dict] = []
    if unknown_aliases:
        issues.append(
            _issue(
                "unknown_alias",
                "Citation aliases must be mapped in the Evidence section.",
                _sorted_ids(unknown_aliases),
            )
        )
    if unknown_evidence_ids:
        issues.append(
            _issue(
                "unknown_evidence_id",
                "Cited evidence ids must be present in retrieved evidence, facts, or calculations.",
                _sorted_ids(unknown_evidence_ids),
            )
        )
    if require_citations and missing_required_ids:
        issues.append(
            _issue(
                "missing_required_evidence",
                "Structured facts and calculations must cite their source evidence ids.",
                _sorted_ids(missing_required_ids),
            )
        )
    if require_citations and not required_ids and available_ids and not extracted["cited_evidence_ids"]:
        issues.append(
            _issue(
                "missing_retrieved_evidence",
                "Answers based on retrieved evidence must cite at least one available evidence id.",
                _sorted_ids(available_ids),
            )
        )

    return {
        "verifier": "CitationChecker",
        "status": _status(issues, extracted),
        "require_citations": require_citations,
        "citation_count": len(extracted["alias_citations"]) + len(extracted["direct_evidence_ids"]),
        "cited_evidence_count": len(extracted["cited_evidence_ids"]),
        "alias_citations": _sorted_ids(extracted["alias_citations"]),
        "direct_evidence_ids": _sorted_ids(extracted["direct_evidence_ids"]),
        "citation_map": dict(sorted(extracted["citation_map"].items())),
        "cited_evidence_ids": _sorted_ids(extracted["cited_evidence_ids"]),
        "available_evidence_ids": _sorted_ids(available_ids),
        "required_evidence_ids": _sorted_ids(required_ids),
        "unknown_aliases": _sorted_ids(unknown_aliases),
        "unknown_evidence_ids": _sorted_ids(unknown_evidence_ids),
        "missing_required_evidence_ids": _sorted_ids(missing_required_ids),
        "issue_count": len(issues),
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check answer citations against available evidence ids.")
    parser.add_argument("answer", help="Answer text to check.")
    parser.add_argument("--evidence-id", action="append", default=[], help="Available evidence id. Can be repeated.")
    parser.add_argument("--require-citations", action="store_true", help="Fail when required evidence is not cited.")
    args = parser.parse_args()

    evidence = [{"id": evidence_id} for evidence_id in args.evidence_id]
    report = check_citations(
        answer=args.answer,
        evidence=evidence,
        require_citations=args.require_citations,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
