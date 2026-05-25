"""Manual repair helpers for cataloging jobs."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ...database.models import CatalogingCandidate, CatalogingChapterRun, CatalogingJob
from .candidate_io import float_or_none
from .constants import VALID_ITEM_TYPES
from .job_control import refresh_job_progress


def create_manual_candidate(
    db: Session,
    job: CatalogingJob,
    run: CatalogingChapterRun,
    item_type: str,
    payload: dict[str, Any],
    status: str,
    target_name: str | None = None,
    confidence: float | None = None,
    evidence: str | None = None,
) -> CatalogingCandidate:
    if item_type not in VALID_ITEM_TYPES:
        raise ValueError(f"Unsupported cataloging item type: {item_type}")
    sort_order = db.query(CatalogingCandidate).filter(CatalogingCandidate.chapter_run_id == run.id).count()
    candidate = CatalogingCandidate(
        job_id=job.id,
        chapter_run_id=run.id,
        project_id=job.project_id,
        chapter_id=run.chapter_id,
        item_type=item_type,
        operation="upsert",
        target_name=(target_name or "")[:200] or None,
        raw_payload=json.dumps(payload, ensure_ascii=False),
        edited_payload=json.dumps(payload, ensure_ascii=False),
        status=status,
        confidence=float_or_none(confidence),
        evidence=(evidence or "")[:2000] or None,
        sort_order=sort_order,
        source_task="manual_repair",
    )
    db.add(candidate)
    db.flush()
    return candidate


def has_usable_chapter_summary(db: Session, run: CatalogingChapterRun) -> bool:
    return (
        db.query(CatalogingCandidate.id)
        .filter(
            CatalogingCandidate.chapter_run_id == run.id,
            CatalogingCandidate.item_type == "chapter_summary",
            CatalogingCandidate.status.notin_(["rejected"]),
        )
        .first()
        is not None
    )


def recover_failed_run_for_review(db: Session, job: CatalogingJob, run: CatalogingChapterRun) -> None:
    run.status = "awaiting_confirmation"
    run.completed_at = run.completed_at or datetime.utcnow()
    run.error = None
    job.status = "waiting_confirmation"
    job.blocked_chapter_id = run.chapter_id
    job.error = None
    refresh_job_progress(db, job)
