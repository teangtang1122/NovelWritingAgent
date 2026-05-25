"""Relationship/link write helpers for cataloging."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...database.models import (
    Chapter,
    ChapterCharacter,
    ChapterWorldbuilding,
    Character,
    OutlineNode,
    OutlineNodeCharacter,
    WorldbuildingEntry,
)
from .lookups import find_character_by_name_or_id


def link_chapter_character(db: Session, chapter: Chapter, character: Character, description: str) -> None:
    existing = db.query(ChapterCharacter).filter(
        ChapterCharacter.chapter_id == chapter.id,
        ChapterCharacter.character_id == character.id,
    ).first()
    if existing:
        if description and not existing.description:
            existing.description = description[:2000]
        return
    db.add(ChapterCharacter(
        chapter_id=chapter.id,
        character_id=character.id,
        appearance_type="出场",
        description=description[:2000],
    ))


def link_chapter_worldbuilding(db: Session, chapter: Chapter, entry: WorldbuildingEntry, description: str) -> None:
    existing = db.query(ChapterWorldbuilding).filter(
        ChapterWorldbuilding.chapter_id == chapter.id,
        ChapterWorldbuilding.worldbuilding_entry_id == entry.id,
    ).first()
    if existing:
        if description and not existing.description:
            existing.description = description[:2000]
        return
    db.add(ChapterWorldbuilding(
        chapter_id=chapter.id,
        worldbuilding_entry_id=entry.id,
        description=description[:2000],
    ))


def link_outline_characters(db: Session, project_id: str, node: OutlineNode, names: Any) -> None:
    if not isinstance(names, list):
        return
    existing_ids = {link.character_id for link in node.linked_characters}
    for name in names:
        character = find_character_by_name_or_id(db, project_id, name)
        if character and character.id not in existing_ids:
            node.linked_characters.append(
                OutlineNodeCharacter(character_id=character.id, role_in_scene="建档关联")
            )
            existing_ids.add(character.id)
