"""Skill management workspace tools."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...skills.service import (
    build_skill_draft,
    create_skill as create_skill_record,
    delete_skill as delete_skill_record,
    ensure_builtin_skills,
    get_skill_or_404,
    list_skill_templates,
    list_skill_tools,
    list_skill_versions,
    list_skills as list_skill_records,
    preview_skill_match,
    reset_skill_to_builtin,
    skill_to_dict,
    update_skill as update_skill_record,
)


def _find_skill_id(db: Session, project_id: str, args: dict[str, Any]) -> str | None:
    skill_id = str(args.get("id") or args.get("skill_id") or "").strip()
    if skill_id:
        return skill_id
    name = str(args.get("name") or "").strip()
    if not name:
        return None
    for skill in list_skill_records(db, project_id):
        if skill.get("name") == name:
            return str(skill.get("id"))
    return None


async def list_skills(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    skills = list_skill_records(db, project_id)
    return {
        "tool": "list_skills",
        "status": "ok",
        "detail": f"共 {len(skills)} 个技能",
        "data": {"items": skills, "total": len(skills)},
    }


async def list_skill_templates_tool(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    templates = list_skill_templates()
    return {
        "tool": "list_skill_templates",
        "status": "ok",
        "detail": f"共 {len(templates)} 个技能模板",
        "data": {"items": templates, "total": len(templates)},
    }


async def list_skill_tools_tool(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    tools = list_skill_tools()
    return {
        "tool": "list_skill_tools",
        "status": "ok",
        "detail": f"共 {len(tools)} 个可推荐工具",
        "data": {"items": tools, "total": len(tools)},
    }


async def draft_skill(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    requirements = str(args.get("requirements") or "").strip()
    if not requirements:
        return {"tool": "draft_skill", "status": "skipped", "detail": "技能需求为空"}
    draft = build_skill_draft(
        requirements,
        template_key=str(args.get("template_key") or "") or None,
        scope=str(args.get("scope") or "global"),
    )
    return {"tool": "draft_skill", "status": "ok", "detail": "已生成技能草案", "data": draft}


async def create_skill(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    if not args.get("system_prompt") and args.get("requirements"):
        draft = build_skill_draft(
            str(args.get("requirements") or ""),
            template_key=str(args.get("template_key") or "") or None,
            scope=str(args.get("scope") or "global"),
        )
        args = {**draft, **{k: v for k, v in args.items() if v not in (None, "", [])}}
    if not args.get("name") or not args.get("system_prompt"):
        return {"tool": "create_skill", "status": "skipped", "detail": "技能名称或系统提示词为空"}
    data = create_skill_record(db, project_id, {
        "name": str(args.get("name")).strip(),
        "description": args.get("description"),
        "trigger_examples": args.get("trigger_examples") if isinstance(args.get("trigger_examples"), list) else [],
        "system_prompt": str(args.get("system_prompt") or ""),
        "recommended_tools": args.get("recommended_tools") if isinstance(args.get("recommended_tools"), list) else [],
        "forbidden_tools": args.get("forbidden_tools") if isinstance(args.get("forbidden_tools"), list) else [],
        "scope": str(args.get("scope") or "global"),
        "priority": int(args.get("priority") or 0),
        "enabled": bool(args.get("enabled") if "enabled" in args else True),
    })
    return {"tool": "create_skill", "status": "ok", "detail": f"已创建技能：{data.get('name')}", "data": data}


async def update_skill(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    skill_id = _find_skill_id(db, project_id, args)
    if not skill_id:
        return {"tool": "update_skill", "status": "skipped", "detail": "未找到技能"}
    update_data = {
        key: args[key]
        for key in [
            "name",
            "description",
            "trigger_examples",
            "system_prompt",
            "recommended_tools",
            "forbidden_tools",
            "scope",
            "priority",
            "enabled",
        ]
        if key in args
    }
    data = update_skill_record(db, project_id, skill_id, update_data)
    return {"tool": "update_skill", "status": "ok", "detail": f"已更新技能：{data.get('name')}", "data": data}


async def delete_skill(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    skill_id = _find_skill_id(db, project_id, args)
    if not skill_id:
        return {"tool": "delete_skill", "status": "skipped", "detail": "未找到技能"}
    skill = get_skill_or_404(db, project_id, skill_id)
    name = skill.name
    delete_skill_record(db, project_id, skill_id)
    return {"tool": "delete_skill", "status": "ok", "detail": f"已删除技能：{name}", "data": {"id": skill_id}}


async def reset_skill(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    skill_id = _find_skill_id(db, project_id, args)
    if not skill_id:
        return {"tool": "reset_skill", "status": "skipped", "detail": "未找到技能"}
    data = reset_skill_to_builtin(db, project_id, skill_id)
    return {"tool": "reset_skill", "status": "ok", "detail": f"已恢复技能默认值：{data.get('name')}", "data": data}


async def preview_skill_match_tool(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    message = str(args.get("message") or "").strip()
    if not message:
        return {"tool": "preview_skill_match", "status": "skipped", "detail": "测试消息为空"}
    data = preview_skill_match(
        db,
        project_id,
        message=message,
        scope=str(args.get("scope") or "project"),
        candidate=args.get("candidate") if isinstance(args.get("candidate"), dict) else None,
    )
    return {"tool": "preview_skill_match", "status": "ok", "detail": "已预览技能匹配", "data": data}


async def list_skill_versions_tool(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    skill_id = _find_skill_id(db, project_id, args)
    if not skill_id:
        return {"tool": "list_skill_versions", "status": "skipped", "detail": "未找到技能"}
    versions = list_skill_versions(db, project_id, skill_id)
    return {
        "tool": "list_skill_versions",
        "status": "ok",
        "detail": f"共 {len(versions)} 个技能版本",
        "data": {"items": versions, "total": len(versions)},
    }


async def ensure_builtin_skills_tool(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    ensure_builtin_skills(db, project_id)
    skills = list_skill_records(db, project_id)
    return {
        "tool": "ensure_builtin_skills",
        "status": "ok",
        "detail": "已确保内置技能存在",
        "data": {"items": skills, "total": len(skills)},
    }
