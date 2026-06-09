"""Prompt pack tools — read public prompt packs and method cards.

These tools are API-free and exposed to internal assistant, scheduler,
and MCP readonly collaboration pack.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session


async def list_prompt_packs(
    db: Session,
    project_id: str,
    args: dict[str, Any],
) -> dict:
    """List available public prompt packs."""
    from app.database.models import PublicPromptPack
    from app.services.prompt_packs.seed import ensure_builtin_packs

    ensure_builtin_packs(db)

    scope = str(args.get("scope") or "").strip()
    query = db.query(PublicPromptPack).filter(PublicPromptPack.enabled == True)
    if scope:
        query = query.filter(PublicPromptPack.scope == scope)

    packs = query.order_by(PublicPromptPack.scope, PublicPromptPack.pack_id).all()

    return {
        "tool": "list_prompt_packs",
        "status": "ok",
        "detail": f"Found {len(packs)} prompt packs",
        "data": {
            "items": [
                {
                    "pack_id": p.pack_id,
                    "version": p.version,
                    "scope": p.scope,
                    "title": p.title,
                    "summary": p.summary,
                    "is_builtin": p.is_builtin,
                }
                for p in packs
            ],
            "total": len(packs),
        },
    }


async def get_prompt_pack(
    db: Session,
    project_id: str,
    args: dict[str, Any],
) -> dict:
    """Get a specific prompt pack by scope and mode."""
    from app.database.models import PublicPromptPack
    from app.services.prompt_packs.seed import ensure_builtin_packs

    ensure_builtin_packs(db)

    scope = str(args.get("scope") or "chapter_writing").strip()
    mode = str(args.get("mode") or "quality").strip()
    pack_id = str(args.get("pack_id") or "").strip()

    # Find by pack_id or by scope+mode
    if pack_id:
        pack = db.query(PublicPromptPack).filter(
            PublicPromptPack.pack_id == pack_id,
            PublicPromptPack.enabled == True,
        ).first()
    else:
        # Map scope+mode to pack_id
        scope_mode_map = {
            ("chapter_writing", "quality"): "chapter_writing_quality",
            ("chapter_writing", "fast"): "chapter_writing_fast",
            ("chapter_review", "quality"): "chapter_review_quality",
            ("new_project", ""): "new_project_setup",
            ("character_design", ""): "character_design",
            ("worldbuilding", ""): "worldbuilding_design",
            ("outline_planning", ""): "outline_planning",
            ("anti_ai_review", ""): "anti_ai_review",
        }
        mapped_id = scope_mode_map.get((scope, mode), scope_mode_map.get((scope, ""), ""))
        if mapped_id:
            pack = db.query(PublicPromptPack).filter(
                PublicPromptPack.pack_id == mapped_id,
                PublicPromptPack.enabled == True,
            ).first()
        else:
            pack = db.query(PublicPromptPack).filter(
                PublicPromptPack.scope == scope,
                PublicPromptPack.enabled == True,
            ).first()

    if not pack:
        return {
            "tool": "get_prompt_pack",
            "status": "skipped",
            "detail": f"Prompt pack not found: scope={scope} mode={mode} pack_id={pack_id}",
            "data": None,
        }

    return {
        "tool": "get_prompt_pack",
        "status": "ok",
        "detail": f"Prompt pack: {pack.title} (v{pack.version})",
        "data": {
            "pack_id": pack.pack_id,
            "version": pack.version,
            "scope": pack.scope,
            "title": pack.title,
            "summary": pack.summary,
            "system_prompt": pack.system_prompt,
            "workflow": pack.workflow_json,
            "quality_rubric": pack.quality_rubric_json,
            "tool_playbook": pack.tool_playbook_json,
            "forbidden_patterns": pack.forbidden_patterns_json,
            "context_policy": pack.context_policy_json,
            "output_contract": pack.output_contract_json,
        },
    }


async def get_tool_playbook(
    db: Session,
    project_id: str,
    args: dict[str, Any],
) -> dict:
    """Get a tool usage playbook for a specific scenario."""
    from app.database.models import PublicPromptPack
    from app.services.prompt_packs.seed import ensure_builtin_packs

    ensure_builtin_packs(db)

    tool_name = str(args.get("tool_name") or "").strip()
    scenario = str(args.get("scenario") or "external_writing").strip()

    if not tool_name:
        return {
            "tool": "get_tool_playbook",
            "status": "skipped",
            "detail": "tool_name is required",
            "data": None,
        }

    # Search all packs for the tool playbook
    packs = db.query(PublicPromptPack).filter(
        PublicPromptPack.enabled == True,
        PublicPromptPack.tool_playbook_json != None,
    ).all()

    for pack in packs:
        playbook = pack.tool_playbook_json or {}
        if tool_name in playbook:
            entry = playbook[tool_name]
            return {
                "tool": "get_tool_playbook",
                "status": "ok",
                "detail": f"Playbook for {tool_name} from {pack.pack_id}",
                "data": {
                    "tool_name": tool_name,
                    "scenario": scenario,
                    "pack_id": pack.pack_id,
                    "playbook": entry,
                },
            }

    return {
        "tool": "get_tool_playbook",
        "status": "skipped",
        "detail": f"No playbook found for tool: {tool_name}",
        "data": None,
    }


async def get_quality_rubric(
    db: Session,
    project_id: str,
    args: dict[str, Any],
) -> dict:
    """Get quality rubric for a specific scope."""
    from app.database.models import PublicPromptPack
    from app.services.prompt_packs.seed import ensure_builtin_packs

    ensure_builtin_packs(db)

    scope = str(args.get("scope") or "chapter_writing").strip()
    pack_id = str(args.get("pack_id") or "").strip()

    if pack_id:
        pack = db.query(PublicPromptPack).filter(
            PublicPromptPack.pack_id == pack_id,
            PublicPromptPack.enabled == True,
        ).first()
    else:
        # Find the quality pack for this scope
        scope_pack_map = {
            "chapter_writing": "chapter_writing_quality",
            "chapter_review": "chapter_review_quality",
        }
        mapped_id = scope_pack_map.get(scope, "")
        if mapped_id:
            pack = db.query(PublicPromptPack).filter(
                PublicPromptPack.pack_id == mapped_id,
                PublicPromptPack.enabled == True,
            ).first()
        else:
            pack = db.query(PublicPromptPack).filter(
                PublicPromptPack.scope == scope,
                PublicPromptPack.enabled == True,
                PublicPromptPack.quality_rubric_json != None,
            ).first()

    if not pack or not pack.quality_rubric_json:
        return {
            "tool": "get_quality_rubric",
            "status": "skipped",
            "detail": f"No quality rubric found for scope: {scope}",
            "data": None,
        }

    return {
        "tool": "get_quality_rubric",
        "status": "ok",
        "detail": f"Quality rubric from {pack.pack_id}",
        "data": {
            "pack_id": pack.pack_id,
            "scope": pack.scope,
            "rubric": pack.quality_rubric_json,
        },
    }
