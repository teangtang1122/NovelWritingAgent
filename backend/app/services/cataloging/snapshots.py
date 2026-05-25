"""Snapshot helpers for cataloging writes."""
from __future__ import annotations

import json
from typing import Any

from ...database.models import Character, Chapter, OutlineNode, WorldbuildingEntry


def character_snapshot(character: Character | None) -> dict | None:
    if not character:
        return None
    abilities: list[str] = []
    if character.abilities:
        try:
            parsed = json.loads(character.abilities)
            abilities = parsed if isinstance(parsed, list) else []
        except Exception:
            abilities = []
    return {
        "id": character.id,
        "name": character.name,
        "appearance": character.appearance,
        "personality": character.personality,
        "background": character.background,
        "abilities": abilities,
        "role_type": character.role_type,
        "life_status": character.life_status,
        "current_location": character.current_location,
        "realm_or_level": character.realm_or_level,
        "physical_state": character.physical_state,
        "mental_state": character.mental_state,
        "current_goal": character.current_goal,
        "active_conflict": character.active_conflict,
        "abilities_state": character.abilities_state,
        "items_or_assets": character.items_or_assets,
    }


def worldbuilding_snapshot(entry: WorldbuildingEntry | None) -> dict | None:
    if not entry:
        return None
    return {
        "id": entry.id,
        "dimension": entry.dimension,
        "title": entry.title,
        "content": entry.content,
        "status": entry.status,
        "confidence": entry.confidence,
    }


def outline_snapshot(node: OutlineNode | None) -> dict | None:
    if not node:
        return None
    return {
        "id": node.id,
        "title": node.title,
        "summary": node.summary,
        "status": node.status,
        "source_chapter_id": node.source_chapter_id,
        "actual_summary": node.actual_summary,
    }


def chapter_change_title(chapter: Chapter, summary: Any) -> str:
    detail = str(summary or "").strip()
    if len(detail) > 80:
        detail = detail[:80] + "..."
    return f"《{chapter.title}》：{detail or '信息更新'}"
