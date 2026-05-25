"""Cataloging candidate serialization helpers."""
from __future__ import annotations

import json
from typing import Any

from ...database.models import CatalogingCandidate


def candidate_payload(candidate: CatalogingCandidate) -> dict[str, Any]:
    text = candidate.edited_payload or candidate.raw_payload
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def candidate_to_dict(candidate: CatalogingCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "job_id": candidate.job_id,
        "chapter_run_id": candidate.chapter_run_id,
        "chapter_id": candidate.chapter_id,
        "item_type": candidate.item_type,
        "operation": candidate.operation,
        "target_type": candidate.target_type,
        "target_id": candidate.target_id,
        "target_name": candidate.target_name,
        "payload": candidate_payload(candidate),
        "status": candidate.status,
        "confidence": candidate.confidence,
        "evidence": candidate.evidence,
        "sort_order": candidate.sort_order,
        "source_task": candidate.source_task,
        "error": candidate.error,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
    }


def float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None
