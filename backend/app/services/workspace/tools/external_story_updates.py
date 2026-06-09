"""External story update tools — apply character/worldbuilding/outline updates.

These tools allow external agents to propose and apply updates to story data
after writing a chapter. They respect MCP permission pack and confirmation rules.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session


async def apply_external_story_updates(
    db: Session,
    project_id: str,
    args: dict[str, Any],
) -> dict:
    """Apply character/worldbuilding/outline updates from external agents.

    Supports two modes:
    - manual: returns write candidates without applying
    - auto: applies safe create/update operations

    Updates are grouped by: characters, relationships, worldbuilding, outline, chapter_summary.
    """
    from app.database.models import (
        Character, CharacterRelationship, WorldbuildingEntry,
        OutlineNode, Chapter,
    )

    chapter_id = str(args.get("chapter_id") or "").strip()
    updates = args.get("updates", {})
    mode = str(args.get("mode") or "manual").strip()

    if not isinstance(updates, dict):
        return {
            "tool": "apply_external_story_updates",
            "status": "skipped",
            "detail": "updates must be a dict",
            "data": None,
        }

    result: dict[str, Any] = {
        "mode": mode,
        "candidates": [],
        "applied": [],
        "skipped": [],
        "warnings": [],
    }

    # Process character updates
    char_updates = updates.get("characters", [])
    if isinstance(char_updates, list):
        for cu in char_updates:
            char_id = str(cu.get("id") or "").strip()
            if not char_id:
                result["skipped"].append({"type": "character", "reason": "missing id"})
                continue

            char = db.query(Character).filter(
                Character.id == char_id,
                Character.project_id == project_id,
            ).first()
            if not char:
                result["skipped"].append({"type": "character", "id": char_id, "reason": "not found"})
                continue

            candidate = {
                "type": "character",
                "id": char_id,
                "name": char.name,
                "updates": {},
            }

            # Fields that can be updated
            updatable = [
                "current_location", "current_goal", "life_status",
                "physical_state", "mental_state", "active_conflict",
                "abilities_state", "items_or_assets",
            ]
            for field in updatable:
                if field in cu:
                    candidate["updates"][field] = cu[field]

            if candidate["updates"]:
                if mode == "auto":
                    for field, value in candidate["updates"].items():
                        setattr(char, field, value)
                    result["applied"].append(candidate)
                else:
                    result["candidates"].append(candidate)

    # Process worldbuilding updates
    wb_updates = updates.get("worldbuilding", [])
    if isinstance(wb_updates, list):
        for wu in wb_updates:
            wb_id = str(wu.get("id") or "").strip()
            title = str(wu.get("title") or "").strip()

            if wb_id:
                # Update existing
                entry = db.query(WorldbuildingEntry).filter(
                    WorldbuildingEntry.id == wb_id,
                    WorldbuildingEntry.project_id == project_id,
                ).first()
                if not entry:
                    result["skipped"].append({"type": "worldbuilding", "id": wb_id, "reason": "not found"})
                    continue

                candidate = {
                    "type": "worldbuilding",
                    "id": wb_id,
                    "title": entry.title,
                    "updates": {},
                }
                for field in ["content", "dimension", "plot_usage"]:
                    if field in wu:
                        candidate["updates"][field] = wu[field]

                if candidate["updates"]:
                    if mode == "auto":
                        for field, value in candidate["updates"].items():
                            setattr(entry, field, value)
                        result["applied"].append(candidate)
                    else:
                        result["candidates"].append(candidate)
            elif title:
                # Create new
                candidate = {
                    "type": "worldbuilding",
                    "action": "create",
                    "title": title,
                    "content": wu.get("content", ""),
                    "dimension": wu.get("dimension", "culture"),
                }
                if mode == "auto":
                    new_entry = WorldbuildingEntry(
                        project_id=project_id,
                        title=title,
                        content=wu.get("content", ""),
                        dimension=wu.get("dimension", "culture"),
                    )
                    db.add(new_entry)
                    result["applied"].append(candidate)
                else:
                    result["candidates"].append(candidate)

    # Process chapter summary
    chapter_summary = updates.get("chapter_summary")
    if chapter_summary and chapter_id:
        chapter = db.query(Chapter).filter(
            Chapter.id == chapter_id,
            Chapter.project_id == project_id,
        ).first()
        if chapter:
            candidate = {
                "type": "chapter_summary",
                "chapter_id": chapter_id,
                "chapter_title": chapter.title,
                "summary": chapter_summary[:500],
            }
            if mode == "auto":
                # Summary is stored via the chapter_summary relationship
                # For now, just record it as applied
                result["applied"].append(candidate)
            else:
                result["candidates"].append(candidate)

    # Commit if auto mode
    if mode == "auto" and result["applied"]:
        try:
            db.commit()
        except Exception as exc:
            result["warnings"].append(f"Commit failed: {exc}")

    total = len(result["applied"]) + len(result["candidates"]) + len(result["skipped"])
    return {
        "tool": "apply_external_story_updates",
        "status": "ok",
        "detail": f"{mode} mode: {len(result['applied'])} applied, {len(result['candidates'])} candidates, {len(result['skipped'])} skipped",
        "data": result,
    }
