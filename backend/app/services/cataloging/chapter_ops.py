"""Chapter-level cataloging writes."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ...database.models import CatalogingCandidate, Chapter, ChapterSummary


def apply_chapter_summary(
    db: Session,
    candidate: CatalogingCandidate,
    chapter: Chapter,
    payload: dict[str, Any],
) -> dict[str, Any]:
    summary_text = str(payload.get("summary_text") or payload.get("summary") or "").strip()
    if not summary_text:
        raise ValueError("章节摘要为空")
    key_events = payload.get("key_events") if isinstance(payload.get("key_events"), list) else []
    old = None
    summary = db.query(ChapterSummary).filter(ChapterSummary.chapter_id == chapter.id).first()
    if not summary:
        summary = ChapterSummary(chapter_id=chapter.id, summary_text=summary_text)
        db.add(summary)
    else:
        old = {"summary_text": summary.summary_text, "key_events": summary.key_events}
        summary.summary_text = summary_text
    summary.key_events = json.dumps([str(item) for item in key_events], ensure_ascii=False)
    summary.ai_model = "cataloging"
    summary.updated_at = datetime.utcnow()
    return {
        "target_type": "chapter_summary",
        "target_id": summary.id,
        "old_value": old,
        "new_value": payload,
        "detail": "章节摘要已更新",
    }
