"""Create cataloging candidates from streamed model lines."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ...database.models import CatalogingCandidate, CatalogingChapterRun, CatalogingJob
from .candidate_io import float_or_none
from .constants import VALID_ITEM_TYPES
from .jsonl import clean_jsonl_text, normalize_candidate, parse_json_line


def try_create_candidate(
    db: Session,
    job: CatalogingJob,
    run: CatalogingChapterRun,
    line: str,
    sort_order: int,
) -> dict[str, Any]:
    text = clean_jsonl_text(line)
    if not text:
        return {}
    try:
        parsed = parse_json_line(text)
        if parsed is None:
            return {}
        normalized = normalize_candidate(parsed)
        if normalized["item_type"] not in VALID_ITEM_TYPES:
            return {"bad_line": text, "error": f"未知 type: {normalized['item_type']}"}
        candidate = CatalogingCandidate(
            job_id=job.id,
            chapter_run_id=run.id,
            project_id=job.project_id,
            chapter_id=run.chapter_id,
            item_type=normalized["item_type"],
            operation=normalized["operation"],
            target_type=normalized.get("target_type"),
            target_id=normalized.get("target_id"),
            target_name=str(normalized.get("target_name") or "")[:200] or None,
            raw_payload=json.dumps(normalized["payload"], ensure_ascii=False),
            status="pending",
            confidence=float_or_none(normalized.get("confidence")),
            evidence=str(normalized.get("evidence") or "")[:2000] or None,
            sort_order=sort_order,
            source_task=normalized.get("source_task"),
        )
        db.add(candidate)
        db.flush()
        return {"candidate": candidate}
    except Exception as exc:
        return {"bad_line": text, "error": str(exc)}
