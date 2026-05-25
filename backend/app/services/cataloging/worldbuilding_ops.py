"""Worldbuilding cataloging writes."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...database.models import (
    CatalogingCandidate,
    Chapter,
    WorldbuildingEntry,
    WorldbuildingTimeline,
    WorldbuildingVersion,
)
from .candidate_io import float_or_none
from .constants import WORLD_DIMENSIONS
from .links import link_chapter_worldbuilding
from .lookups import find_worldbuilding_by_title_or_id, next_worldbuilding_sort_order
from .snapshots import chapter_change_title, worldbuilding_snapshot


def apply_worldbuilding(
    db: Session,
    candidate: CatalogingCandidate,
    chapter: Chapter,
    payload: dict[str, Any],
    create: bool,
) -> dict:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("世界观标题为空")
    dimension = _normalize_dimension(payload.get("dimension"))
    entry = find_worldbuilding_by_title_or_id(db, chapter.project_id, payload.get("id") or title)
    old = worldbuilding_snapshot(entry) if entry else None
    if not entry:
        entry = WorldbuildingEntry(
            project_id=chapter.project_id,
            dimension=dimension,
            title=title[:200],
            content=str(payload.get("content") or "")[:12000],
            sort_order=next_worldbuilding_sort_order(db, chapter.project_id, dimension),
            first_seen_chapter_id=chapter.id,
            last_updated_chapter_id=chapter.id,
            status="active",
            confidence=float_or_none(candidate.confidence),
        )
        db.add(entry)
        db.flush()
    else:
        entry.dimension = dimension
        if payload.get("content"):
            entry.content = str(payload.get("content"))[:12000]
        entry.title = title[:200]
        entry.last_updated_chapter_id = chapter.id
        entry.confidence = float_or_none(candidate.confidence) or entry.confidence
    ensure_worldbuilding_version(db, entry, chapter, payload)
    link_chapter_worldbuilding(db, chapter, entry, str(payload.get("description") or payload.get("evidence") or ""))
    return {
        "target_type": "worldbuilding",
        "target_id": entry.id,
        "old_value": old,
        "new_value": worldbuilding_snapshot(entry),
        "detail": f"世界观已写入: {entry.title}",
    }


def apply_worldbuilding_timeline(db: Session, candidate: CatalogingCandidate, chapter: Chapter, payload: dict[str, Any]) -> dict:
    entry = find_worldbuilding_by_title_or_id(db, chapter.project_id, payload.get("id") or payload.get("title"))
    if not entry:
        dimension = _normalize_dimension(payload.get("dimension"))
        entry = WorldbuildingEntry(
            project_id=chapter.project_id,
            dimension=dimension,
            title=str(payload.get("title") or "未命名设定")[:200],
            content=str(payload.get("event_description") or payload.get("content") or "")[:12000],
            sort_order=next_worldbuilding_sort_order(db, chapter.project_id, dimension),
            first_seen_chapter_id=chapter.id,
            last_updated_chapter_id=chapter.id,
        )
        db.add(entry)
        db.flush()
        ensure_worldbuilding_version(db, entry, chapter, payload)
    event = WorldbuildingTimeline(
        entry_id=entry.id,
        chapter_id=chapter.id,
        event_description=str(payload.get("event_description") or payload.get("description") or "")[:4000],
        event_type=str(payload.get("event_type") or "fact_change")[:50],
        evidence=str(payload.get("evidence") or candidate.evidence or "")[:2000],
        sort_order=int(payload.get("sort_order") or 0),
    )
    if not event.event_description:
        raise ValueError("世界观时间线事件为空")
    db.add(event)
    link_chapter_worldbuilding(db, chapter, entry, event.event_description)
    return {
        "target_type": "worldbuilding_timeline",
        "target_id": event.id,
        "old_value": None,
        "new_value": payload,
        "detail": f"世界观时间线已写入: {entry.title}",
    }


def ensure_worldbuilding_version(
    db: Session,
    entry: WorldbuildingEntry,
    chapter: Chapter,
    payload: dict[str, Any],
) -> None:
    current = db.query(func.max(WorldbuildingVersion.version_number)).filter(
        WorldbuildingVersion.entry_id == entry.id
    ).scalar() or 0
    db.add(WorldbuildingVersion(
        entry_id=entry.id,
        version_number=int(current) + 1,
        snapshot_data=json.dumps(worldbuilding_snapshot(entry), ensure_ascii=False),
        change_summary=chapter_change_title(
            chapter,
            payload.get("change_summary") or payload.get("event_description") or "设定更新",
        ),
        source_chapter_id=chapter.id,
    ))


def _normalize_dimension(value: Any) -> str:
    dimension = str(value or "culture")
    return dimension if dimension in WORLD_DIMENSIONS else "culture"
