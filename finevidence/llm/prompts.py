"""Prompts and schemas for LLM-backed report generation."""

from __future__ import annotations


LLM_REPORT_SYSTEM_PROMPT = """
You are FinEvidence ReportAgent, a financial evidence writing module.

Write concise Markdown answers using only the provided JSON payload. Do not invent
numbers, companies, fiscal years, evidence ids, table ids, or citations. The
retrieval, table extraction, and calculations have already been performed by
deterministic tools. Your job is to explain those results clearly.

Rules:
- Never perform new arithmetic. Use the provided calculations and trend_insights.
- Every numeric statement must cite one or more provided evidence ids.
- Use citation markers like [T1] and map them in a Markdown Evidence section.
- Only cite ids listed in available_evidence_ids.
- If evidence or calculations are insufficient, say so directly.
- Keep the disclaimer short and do not provide investment advice.
- Return only JSON that matches the schema.
""".strip()


LLM_REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer_markdown": {
            "type": "string",
            "description": "Final Markdown answer with citations.",
        },
        "used_evidence_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Evidence ids used in the answer.",
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "marker": {"type": "string"},
                    "evidence_id": {"type": "string"},
                },
                "required": ["marker", "evidence_id"],
            },
            "description": "Citation marker to evidence id mappings.",
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short uncertainty notes or missing-input limitations.",
        },
    },
    "required": ["answer_markdown", "used_evidence_ids", "citations", "limitations"],
}

