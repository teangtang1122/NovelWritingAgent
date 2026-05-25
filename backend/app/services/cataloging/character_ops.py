"""Character cataloging writes."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ...database.models import (
    CatalogingCandidate,
    Chapter,
    Character,
    CharacterAIConfig,
    CharacterTimeline,
    CharacterVersion,
)
from .links import link_chapter_character
from .lookups import find_character_by_name_or_id
from .snapshots import character_snapshot, chapter_change_title


CHARACTER_TEXT_FIELDS = ["appearance", "personality", "background", "role_type"]
CHARACTER_STATE_FIELDS = [
    "life_status",
    "current_location",
    "realm_or_level",
    "physical_state",
    "mental_state",
    "current_goal",
    "active_conflict",
    "abilities_state",
    "items_or_assets",
]


def apply_character_create(db: Session, candidate: CatalogingCandidate, chapter: Chapter, payload: dict[str, Any]) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("角色名为空")
    character = find_character_by_name_or_id(db, chapter.project_id, name)
    old = character_snapshot(character) if character else None
    if not character:
        character = Character(project_id=chapter.project_id, name=name[:100], current_version=1, is_evolution_tracked=True)
        db.add(character)
        db.flush()
    fill_character_fields(db, character, chapter, payload)
    ensure_character_version(db, character, chapter, payload, old is None)
    link_chapter_character(db, chapter, character, str(payload.get("role_in_scene") or "出场"))
    return _character_result(character, old, f"角色已写入: {character.name}")


def apply_character_update(db: Session, candidate: CatalogingCandidate, chapter: Chapter, payload: dict[str, Any]) -> dict:
    character = find_character_by_name_or_id(db, chapter.project_id, payload.get("id") or payload.get("name"))
    if not character:
        return apply_character_create(db, candidate, chapter, payload)
    old = character_snapshot(character)
    fill_character_fields(db, character, chapter, payload)
    ensure_character_version(db, character, chapter, payload, False)
    link_chapter_character(db, chapter, character, str(payload.get("role_in_scene") or "提及"))
    return _character_result(character, old, f"角色已更新: {character.name}")


def apply_character_state(db: Session, candidate: CatalogingCandidate, chapter: Chapter, payload: dict[str, Any]) -> dict:
    character = find_character_by_name_or_id(db, chapter.project_id, payload.get("id") or payload.get("name"))
    if not character:
        character = Character(project_id=chapter.project_id, name=str(payload.get("name") or "未命名角色")[:100], current_version=1)
        db.add(character)
        db.flush()
    old = character_snapshot(character)
    changed = False
    for field in CHARACTER_STATE_FIELDS:
        if field in payload and payload.get(field) not in (None, ""):
            setattr(character, field, str(payload.get(field))[:4000])
            changed = True
    character.last_seen_chapter_id = chapter.id
    character.last_updated_chapter_id = chapter.id
    character.updated_at = datetime.utcnow()
    if changed:
        ensure_character_version(db, character, chapter, payload, False)
    link_chapter_character(db, chapter, character, "状态变化")
    return _character_result(character, old, f"角色状态已更新: {character.name}")


def apply_character_timeline(db: Session, candidate: CatalogingCandidate, chapter: Chapter, payload: dict[str, Any]) -> dict:
    character = find_character_by_name_or_id(db, chapter.project_id, payload.get("id") or payload.get("name"))
    if not character:
        raise ValueError("时间线关联角色不存在")
    event = CharacterTimeline(
        character_id=character.id,
        chapter_id=chapter.id,
        event_description=str(payload.get("event_description") or payload.get("description") or "")[:4000],
        event_type=str(payload.get("event_type") or "key_event")[:50],
        emotional_state_change=str(payload.get("emotional_state_change") or "")[:2000],
        sort_order=int(payload.get("sort_order") or 0),
    )
    if not event.event_description:
        raise ValueError("角色时间线事件为空")
    db.add(event)
    link_chapter_character(db, chapter, character, "时间线")
    return {
        "target_type": "character_timeline",
        "target_id": event.id,
        "old_value": None,
        "new_value": payload,
        "detail": f"角色时间线已写入: {character.name}",
    }


def fill_character_fields(db: Session, character: Character, chapter: Chapter, payload: dict[str, Any]) -> None:
    for field in CHARACTER_TEXT_FIELDS:
        if field in payload and payload.get(field) not in (None, ""):
            limit = 100 if field == "role_type" else 8000
            setattr(character, field, str(payload.get(field))[:limit])
    if isinstance(payload.get("abilities"), list):
        character.abilities = json.dumps([str(item) for item in payload["abilities"]], ensure_ascii=False)
    for field in CHARACTER_STATE_FIELDS:
        if field in payload and payload.get(field) not in (None, ""):
            setattr(character, field, str(payload.get(field))[:4000])
    character.last_seen_chapter_id = chapter.id
    character.last_updated_chapter_id = chapter.id
    character.updated_at = datetime.utcnow()
    _update_ai_config(db, character, payload)


def ensure_character_version(
    db: Session,
    character: Character,
    chapter: Chapter,
    payload: dict[str, Any],
    is_create: bool,
) -> None:
    if not is_create:
        character.current_version = (character.current_version or 1) + 1
    db.add(CharacterVersion(
        character_id=character.id,
        version_number=character.current_version or 1,
        snapshot_data=json.dumps(character_snapshot(character), ensure_ascii=False),
        change_summary=chapter_change_title(
            chapter,
            payload.get("change_summary") or payload.get("event_description") or "角色档案更新",
        ),
        source_chapter_id=chapter.id,
    ))


def _update_ai_config(db: Session, character: Character, payload: dict[str, Any]) -> None:
    prompt = str(payload.get("custom_system_prompt") or "").strip()
    if not prompt:
        return
    config = character.ai_config or db.query(CharacterAIConfig).filter(CharacterAIConfig.character_id == character.id).first()
    if not config:
        config = CharacterAIConfig(character_id=character.id)
        db.add(config)
    config.custom_system_prompt = prompt[:12000]


def _character_result(character: Character, old: dict | None, detail: str) -> dict:
    return {
        "target_type": "character",
        "target_id": character.id,
        "old_value": old,
        "new_value": character_snapshot(character),
        "detail": detail,
    }
