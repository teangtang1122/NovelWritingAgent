"""Outline cataloging writes."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...database.models import CatalogingCandidate, Chapter, OutlineNode
from .links import link_outline_characters
from .lookups import find_outline_by_title_or_id, next_outline_sort_order
from .snapshots import outline_snapshot


def apply_outline(
    db: Session,
    candidate: CatalogingCandidate,
    chapter: Chapter,
    payload: dict[str, Any],
    create: bool,
) -> dict[str, Any]:
    title = str(payload.get("title") or payload.get("target_name") or chapter.title).strip()
    if not title:
        raise ValueError("大纲标题为空")
    node = find_outline_by_title_or_id(db, chapter.project_id, payload.get("id") or title)
    old = outline_snapshot(node) if node else None
    if not node:
        node = OutlineNode(
            project_id=chapter.project_id,
            parent_id=None,
            node_type=str(payload.get("node_type") or "chapter")[:20],
            title=title[:200],
            summary=str(payload.get("summary") or payload.get("actual_summary") or "")[:8000],
            status=str(payload.get("status") or "completed")[:20],
            source_chapter_id=chapter.id,
            actual_summary=str(payload.get("actual_summary") or payload.get("summary") or "")[:8000],
            cataloging_status="cataloged",
            sort_order=next_outline_sort_order(db, chapter.project_id, None),
        )
        db.add(node)
        db.flush()
    else:
        if payload.get("title"):
            node.title = title[:200]
        if payload.get("summary") or payload.get("actual_summary"):
            node.summary = str(payload.get("summary") or payload.get("actual_summary"))[:8000]
            node.actual_summary = str(payload.get("actual_summary") or payload.get("summary"))[:8000]
        if payload.get("status"):
            node.status = str(payload.get("status"))[:20]
        node.source_chapter_id = node.source_chapter_id or chapter.id
        node.cataloging_status = "cataloged"

    chapter.outline_node_id = node.id
    link_outline_characters(db, chapter.project_id, node, payload.get("related_characters"))
    return {
        "target_type": "outline_node",
        "target_id": node.id,
        "old_value": old,
        "new_value": outline_snapshot(node),
        "detail": "大纲节点已写入",
    }
