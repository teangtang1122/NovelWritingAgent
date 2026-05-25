"""Context builders for per-chapter cataloging."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ...database.models import Chapter, Character, ChapterSummary, OutlineNode, WorldbuildingEntry
from ...services.outline_service import load_outline_nodes, outline_sort_context


def ordered_chapters(db: Session, project_id: str, chapter_ids: list[str] | None = None) -> list[Chapter]:
    outline_context = outline_sort_context(load_outline_nodes(db, project_id))
    query = db.query(Chapter).filter(Chapter.project_id == project_id)
    chapters = query.all()
    by_id = {chapter.id: chapter for chapter in chapters}
    if chapter_ids:
        return [by_id[item] for item in chapter_ids if item in by_id]

    def sort_key(chapter: Chapter):
        outline_key = outline_context["sort_keys"].get(chapter.outline_node_id)
        if outline_key is None:
            return (1, (999999,), chapter.created_at)
        return (0, outline_key, chapter.created_at)

    return sorted(chapters, key=sort_key)


def build_light_context(db: Session, project_id: str, chapter: Chapter) -> dict:
    chapters = ordered_chapters(db, project_id)
    index = next((idx for idx, item in enumerate(chapters) if item.id == chapter.id), 0)
    recent = chapters[max(0, index - 5):index]
    recent_summaries = []
    for item in recent:
        summary = db.query(ChapterSummary).filter(ChapterSummary.chapter_id == item.id).first()
        if summary:
            recent_summaries.append({
                "title": item.title,
                "summary": summary.summary_text[:600],
                "key_events": _parse_list(summary.key_events)[:6],
            })

    characters = (
        db.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.updated_at.desc())
        .limit(120)
        .all()
    )
    world_entries = (
        db.query(WorldbuildingEntry)
        .filter(WorldbuildingEntry.project_id == project_id)
        .order_by(WorldbuildingEntry.updated_at.desc())
        .limit(120)
        .all()
    )
    outline_nodes = (
        db.query(OutlineNode)
        .filter(OutlineNode.project_id == project_id)
        .order_by(OutlineNode.sort_order.asc(), OutlineNode.created_at.asc())
        .limit(160)
        .all()
    )
    previous_states = []
    for character in characters[:30]:
        state = {
            "name": character.name,
            "life_status": character.life_status,
            "current_location": character.current_location,
            "realm_or_level": character.realm_or_level,
            "physical_state": character.physical_state,
            "current_goal": character.current_goal,
        }
        if any(value for key, value in state.items() if key != "name"):
            previous_states.append(state)

    return {
        "recent_chapter_summaries": recent_summaries,
        "character_index": [
            {
                "name": item.name,
                "role_type": item.role_type,
                "aliases": [],
            }
            for item in characters
        ],
        "worldbuilding_index": [
            {"dimension": item.dimension, "title": item.title}
            for item in world_entries
        ],
        "nearby_outline_nodes": [
            {"title": item.title, "node_type": item.node_type, "summary": (item.summary or "")[:240]}
            for item in outline_nodes[max(0, index - 8): index + 12]
        ],
        "previous_character_states": previous_states,
    }


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except Exception:
        return []
    return []
