
"""Rule-based evaluation metrics for FinEvidence predictions."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from statistics import mean


DEFAULT_NUMERIC_TOLERANCE = Decimal("0.0001")


def _to_decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "").replace("%", ""))
    except (InvalidOperation, AttributeError, TypeError, ValueError):
        return None


def _score(values: list[float]) -> float | None:
    if not values:
        return None
    return round(mean(values), 4)


def _prediction_evidence_ids(prediction: dict) -> set[str]:
    evidence_ids: set[str] = set()

    for record in prediction.get("evidence", []):
        for field in ("id", "source_table_id", "table_id", "chunk_id"):
            if record.get(field):
                evidence_ids.add(str(record[field]))

    for record in prediction.get("calculations", []):
        evidence_ids.update(str(table_id) for table_id in record.get("source_table_ids", []) if table_id)

    for record in prediction.get("facts", []):
        if record.get("source_table_id"):
            evidence_ids.add(str(record["source_table_id"]))

    for claim in prediction.get("claims", []):
        evidence_ids.update(str(table_id) for table_id in claim.get("source_table_ids", []) if table_id)

    verifier_report = prediction.get("verifier_report", {})
    evidence_report = verifier_report.get("evidence_report") or prediction.get("evidence_verification_report", {})
    for check in evidence_report.get("claim_checks", []):
        evidence_ids.update(str(evidence_id) for evidence_id in check.get("evidence_ids", []) if evidence_id)

    return evidence_ids


def _prediction_number_records(prediction: dict) -> list[dict]:
    records: list[dict] = []

    for record in prediction.get("calculations", []):
        records.append(
            {
                "metric": record.get("metric"),
                "period": str(record.get("period")),
                "value": record.get("result"),
            }
        )

    for record in prediction.get("facts", []):
        records.append(
            {
                "metric": record.get("metric"),
                "period": str(record.get("period")),
                "value": record.get("value"),
            }
        )

    for claim in prediction.get("claims", []):
        if claim.get("value") is not None:
            records.append(
                {
                    "metric": claim.get("metric"),
                    "period": str(claim.get("period")),
                    "value": claim.get("value"),
                }
            )

    return records


def _number_matches(gold: dict, prediction_records: list[dict]) -> bool:
    gold_value = _to_decimal(gold.get("value"))
    if gold_value is None:
        return False

    tolerance = _to_decimal(gold.get("tolerance")) or DEFAULT_NUMERIC_TOLERANCE
    for record in prediction_records:
        if gold.get("metric") and str(record.get("metric")) != str(gold.get("metric")):
            continue
        if gold.get("period") and str(record.get("period")) != str(gold.get("period")):
            continue
        predicted_value = _to_decimal(record.get("value"))
        if predicted_value is None:
            continue
        if abs(predicted_value - gold_value) <= tolerance:
            return True
    return False


def _numeric_status(prediction: dict) -> str:
    verifier_report = prediction.get("verifier_report", {})
    numeric_report = verifier_report.get("numeric_report") or prediction.get("verification_report", {})
    return str(numeric_report.get("status", "not_applicable"))


def _evidence_status(prediction: dict) -> str:
    verifier_report = prediction.get("verifier_report", {})
    evidence_report = verifier_report.get("evidence_report") or prediction.get("evidence_verification_report", {})
    return str(evidence_report.get("status", "not_applicable"))


def _citation_status(prediction: dict) -> str:
    verifier_report = prediction.get("verifier_report", {})
    citation_report = verifier_report.get("citation_report") or prediction.get("citation_report", {})
    return str(citation_report.get("status", "not_applicable"))


def _tool_success(prediction: dict) -> float:
    if prediction.get("error"):
        return 0.0
    answer = str(prediction.get("answer", "")).strip()
    if not answer:
        return 0.0
    failed_steps = [
        step
        for step in prediction.get("steps", [])
        if step.get("status") in {"failed", "error"}
    ]
    return 0.0 if failed_steps else 1.0


def _answer_accuracy(example: dict, record: dict) -> float | None:
    required_phrases = example.get("gold_answer_contains", [])
    if required_phrases:
        answer = str(record.get("answer", "")).lower()
        return 1.0 if all(str(phrase).lower() in answer for phrase in required_phrases) else 0.0

    if example.get("gold_numbers"):
        return record["numeric_match"]
    if example.get("gold_evidence_ids"):
        return 1.0 if record["evidence_recall"] > 0 else 0.0
    return None


def evaluate_prediction(example: dict, prediction: dict) -> dict:
    """Evaluate one orchestrator prediction against one gold example."""

    gold_evidence_ids = {str(evidence_id) for evidence_id in example.get("gold_evidence_ids", [])}
    predicted_evidence_ids = _prediction_evidence_ids(prediction)
    if gold_evidence_ids:
        evidence_hits = gold_evidence_ids & predicted_evidence_ids
        evidence_recall = len(evidence_hits) / len(gold_evidence_ids)
    else:
        evidence_hits = set()
        evidence_recall = None

    gold_numbers = example.get("gold_numbers", [])
    prediction_numbers = _prediction_number_records(prediction)
    if gold_numbers:
        matched_numbers = [gold for gold in gold_numbers if _number_matches(gold, prediction_numbers)]
        numeric_match = len(matched_numbers) / len(gold_numbers)
    else:
        matched_numbers = []
        numeric_match = None

    numeric_status = _numeric_status(prediction)
    evidence_status = _evidence_status(prediction)
    citation_status = _citation_status(prediction)
    if gold_numbers:
        numeric_consistency = 1.0 if numeric_match == 1.0 and numeric_status == "passed" else 0.0
    else:
        numeric_consistency = 0.0 if numeric_status == "numeric_error" else 1.0

    hallucination_free = 1.0 if evidence_status in {"supported", "not_applicable"} else 0.0
    citation_accuracy = None
    if citation_status != "not_applicable":
        citation_accuracy = 1.0 if citation_status == "passed" else 0.0
    tool_success = _tool_success(prediction)

    record = {
        "id": example.get("id"),
        "question_type": example.get("question_type"),
        "ticker": example.get("ticker"),
        "answer_present": bool(str(prediction.get("answer", "")).strip()),
        "evidence_recall": None if evidence_recall is None else round(evidence_recall, 4),
        "evidence_hits": sorted(evidence_hits),
        "numeric_match": None if numeric_match is None else round(numeric_match, 4),
        "matched_gold_numbers": len(matched_numbers),
        "gold_number_count": len(gold_numbers),
        "numeric_consistency": numeric_consistency,
        "hallucination_free": hallucination_free,
        "citation_accuracy": citation_accuracy,
        "tool_success": tool_success,
        "numeric_status": numeric_status,
        "evidence_status": evidence_status,
        "citation_status": citation_status,
        "verifier_status": prediction.get("verifier_report", {}).get("status"),
        "answer": prediction.get("answer", ""),
        "error": prediction.get("error"),
    }
    record["answer_accuracy"] = _answer_accuracy(example, record)
    return record


def summarize_results(records: list[dict]) -> dict:
    """Aggregate per-example evaluation records into headline metrics."""

    if not records:
        return {
            "count": 0,
            "answer_accuracy": None,
            "evidence_recall": None,
            "numeric_consistency": None,
            "citation_accuracy": None,
            "hallucination_rate": None,
            "tool_success_rate": None,
            "numeric_pass_rate": None,
            "evidence_support_rate": None,
            "citation_pass_rate": None,
        }

    answer_scores = [record["answer_accuracy"] for record in records if record.get("answer_accuracy") is not None]
    evidence_scores = [record["evidence_recall"] for record in records if record.get("evidence_recall") is not None]
    citation_scores = [record["citation_accuracy"] for record in records if record.get("citation_accuracy") is not None]

    return {
        "count": len(records),
        "answer_accuracy": _score(answer_scores),
        "evidence_recall": _score(evidence_scores),
        "numeric_consistency": _score([record["numeric_consistency"] for record in records]),
        "citation_accuracy": _score(citation_scores),
        "hallucination_rate": round(1.0 - mean(record["hallucination_free"] for record in records), 4),
        "tool_success_rate": _score([record["tool_success"] for record in records]),
        "numeric_pass_rate": _score([1.0 if record["numeric_status"] in {"passed", "not_applicable"} else 0.0 for record in records]),
        "evidence_support_rate": _score([1.0 if record["evidence_status"] in {"supported", "not_applicable"} else 0.0 for record in records]),
        "citation_pass_rate": _score([1.0 if record["citation_status"] in {"passed", "not_applicable"} else 0.0 for record in records]),
    }
