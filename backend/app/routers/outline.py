"""Outline tree CRUD, reorder, and AI suggestion endpoints."""
import json
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..ai.gateway import LLMGateway
from ..core.exceptions import NotFoundError, ValidationError
from ..core.response import ApiResponse
from ..database.models import (
    Character,
    OutlineNode,
    OutlineNodeCharacter,
    Project,
    WorldbuildingEntry,
)
from ..database.session import get_db
from ..schemas.outline import (
    OutlineAISuggestRequest,
    OutlineCharacterLinkInput,
    OutlineNodeCreate,
    OutlineNodeUpdate,
    OutlineReorderItem,
    OutlineReorderRequest,
)

router = APIRouter(tags=["outline"])


NODE_TYPE_LABELS = {
    "volume": "卷",
    "chapter": "章",
    "section": "节",
}

STATUS_LABELS = {
    "pending": "待规划",
    "in_progress": "进行中",
    "completed": "已完成",
}


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundError("作品不存在")
    return project


def _get_node_or_404(db: Session, project_id: str, node_id: str) -> OutlineNode:
    node = (
        db.query(OutlineNode)
        .filter(OutlineNode.id == node_id, OutlineNode.project_id == project_id)
        .first()
    )
    if not node:
        raise NotFoundError("大纲节点不存在")
    return node


def _get_parent_or_404(db: Session, project_id: str, parent_id: Optional[str]) -> Optional[OutlineNode]:
    if not parent_id:
        return None
    return _get_node_or_404(db, project_id, parent_id)


def _ensure_no_cycle(
    db: Session,
    project_id: str,
    node_id: Optional[str],
    parent_id: Optional[str],
) -> None:
    if not node_id or not parent_id:
        return
    if node_id == parent_id:
        raise ValidationError("节点不能成为自己的父节点")

    current = _get_parent_or_404(db, project_id, parent_id)
    visited: set[str] = set()
    while current:
        if current.id == node_id:
            raise ValidationError("不能把节点移动到自己的子节点下")
        if current.id in visited:
            raise ValidationError("检测到循环大纲结构")
        visited.add(current.id)
        current = (
            db.query(OutlineNode)
            .filter(OutlineNode.id == current.parent_id, OutlineNode.project_id == project_id)
            .first()
            if current.parent_id
            else None
        )


def _extract_character_links(
    character_ids: Optional[list[str]],
    characters: Optional[list[OutlineCharacterLinkInput]],
) -> Optional[list[tuple[str, Optional[str]]]]:
    if characters is not None:
        raw_links = [(item.character_id, item.role_in_scene) for item in characters]
    elif character_ids is not None:
        raw_links = [(character_id, None) for character_id in character_ids]
    else:
        return None

    links: list[tuple[str, Optional[str]]] = []
    seen: set[str] = set()
    for character_id, role_in_scene in raw_links:
        if character_id in seen:
            continue
        seen.add(character_id)
        links.append((character_id, role_in_scene))
    return links


def _replace_character_links(
    db: Session,
    project_id: str,
    node: OutlineNode,
    links: Optional[list[tuple[str, Optional[str]]]],
) -> None:
    if links is None:
        return

    character_ids = [character_id for character_id, _role in links]
    if character_ids:
        count = (
            db.query(Character)
            .filter(Character.project_id == project_id, Character.id.in_(character_ids))
            .count()
        )
        if count != len(character_ids):
            raise ValidationError("关联角色必须属于当前作品")

    node.linked_characters.clear()
    db.flush()
    for character_id, role_in_scene in links:
        node.linked_characters.append(
            OutlineNodeCharacter(character_id=character_id, role_in_scene=role_in_scene)
        )


def _node_to_dict(node: OutlineNode) -> dict:
    return {
        "id": node.id,
        "project_id": node.project_id,
        "parent_id": node.parent_id,
        "node_type": node.node_type,
        "node_type_label": NODE_TYPE_LABELS.get(node.node_type, node.node_type),
        "title": node.title,
        "summary": node.summary,
        "status": node.status,
        "status_label": STATUS_LABELS.get(node.status, node.status),
        "sort_order": node.sort_order,
        "linked_characters": [
            {
                "id": link.character.id,
                "name": link.character.name,
                "role_type": link.character.role_type,
                "role_in_scene": link.role_in_scene,
            }
            for link in sorted(
                node.linked_characters,
                key=lambda item: item.created_at,
            )
            if link.character is not None
        ],
        "children": [],
        "created_at": node.created_at.isoformat() if node.created_at else None,
        "updated_at": node.updated_at.isoformat() if node.updated_at else None,
    }


def _load_outline_nodes(db: Session, project_id: str) -> list[OutlineNode]:
    return (
        db.query(OutlineNode)
        .filter(OutlineNode.project_id == project_id)
        .order_by(OutlineNode.sort_order.asc(), OutlineNode.created_at.asc())
        .all()
    )


def _build_outline_payload(nodes: list[OutlineNode]) -> dict:
    node_map = {node.id: _node_to_dict(node) for node in nodes}
    roots: list[dict] = []
    for node in nodes:
        item = node_map[node.id]
        parent = node_map.get(node.parent_id) if node.parent_id else None
        if parent is None:
            roots.append(item)
        else:
            parent["children"].append(item)

    return {
        "items": roots,
        "flat": [node_map[node.id] for node in nodes],
        "total": len(nodes),
    }


def _outline_payload(db: Session, project_id: str) -> dict:
    return _build_outline_payload(_load_outline_nodes(db, project_id))


def _normalize_reorder_items(payload: OutlineReorderRequest) -> list[OutlineReorderItem]:
    if payload.sort_order is not None:
        return [
            OutlineReorderItem(id=node_id, parent_id=payload.parent_id, sort_order=index)
            for index, node_id in enumerate(payload.sort_order)
        ]
    return payload.items


@router.get("/projects/{project_id}/outline")
def get_outline(project_id: str, db: Session = Depends(get_db)):
    """Get the full outline tree for a project."""
    _get_project_or_404(db, project_id)
    return ApiResponse.success(data=_outline_payload(db, project_id))


@router.post("/projects/{project_id}/outline")
def create_outline_node(
    project_id: str,
    payload: OutlineNodeCreate,
    db: Session = Depends(get_db),
):
    """Create an outline node."""
    _get_project_or_404(db, project_id)
    _get_parent_or_404(db, project_id, payload.parent_id)

    node = OutlineNode(
        project_id=project_id,
        parent_id=payload.parent_id,
        node_type=payload.node_type,
        title=payload.title,
        summary=payload.summary,
        status=payload.status,
        sort_order=payload.sort_order,
    )
    db.add(node)
    db.flush()
    links = _extract_character_links(payload.character_ids, payload.characters)
    _replace_character_links(db, project_id, node, links or [])
    db.commit()
    db.refresh(node)
    return ApiResponse.success(data=_node_to_dict(node), message="大纲节点已创建")


@router.put("/projects/{project_id}/outline/reorder")
def reorder_outline(
    project_id: str,
    payload: OutlineReorderRequest,
    db: Session = Depends(get_db),
):
    """Reorder outline nodes and optionally move them to a new parent."""
    _get_project_or_404(db, project_id)
    items = _normalize_reorder_items(payload)
    if not items:
        raise ValidationError("未提供排序数据")

    touched_ids = [item.id for item in items]
    nodes = (
        db.query(OutlineNode)
        .filter(OutlineNode.project_id == project_id, OutlineNode.id.in_(touched_ids))
        .all()
    )
    node_by_id = {node.id: node for node in nodes}
    if len(node_by_id) != len(set(touched_ids)):
        raise ValidationError("排序节点必须属于当前作品")

    for item in items:
        node = node_by_id[item.id]
        _get_parent_or_404(db, project_id, item.parent_id)
        _ensure_no_cycle(db, project_id, node.id, item.parent_id)
        node.parent_id = item.parent_id
        node.sort_order = item.sort_order

    db.commit()
    return ApiResponse.success(data=_outline_payload(db, project_id), message="大纲排序已更新")


def _strip_json_fence(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return raw


def _parse_outline_ai_suggestions(text: str, fallback_type: str, limit: int) -> list[dict]:
    suggestions: list[dict] = []
    try:
        parsed = json.loads(_strip_json_fence(text))
        items = parsed.get("suggestions") if isinstance(parsed, dict) else parsed
        if isinstance(items, list):
            for item in items[:limit]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                summary = str(item.get("summary") or "").strip()
                if not title or not summary:
                    continue
                node_type = str(item.get("node_type") or fallback_type).strip()
                if node_type not in {"volume", "chapter", "section"}:
                    node_type = fallback_type
                character_names = [
                    str(name).strip()
                    for name in (item.get("character_names") or [])
                    if str(name).strip()
                ]
                suggestions.append({
                    "title": title[:200],
                    "summary": summary,
                    "node_type": node_type,
                    "character_names": character_names[:12],
                })
    except (json.JSONDecodeError, TypeError, AttributeError):
        suggestions = []
    return suggestions


@router.post("/projects/{project_id}/outline/ai-suggest")
async def ai_suggest_outline_structured(
    project_id: str,
    payload: OutlineAISuggestRequest,
    db: Session = Depends(get_db),
):
    """Generate structured continuous outline suggestions."""
    project = _get_project_or_404(db, project_id)
    node = _get_node_or_404(db, project_id, payload.node_id) if payload.node_id else None
    parent = (
        db.query(OutlineNode)
        .filter(OutlineNode.id == node.parent_id, OutlineNode.project_id == project_id)
        .first()
        if node and node.parent_id
        else None
    )
    suggestion_count = max(1, min(payload.suggestion_count or 1, 8))
    fallback_type = "section" if node and node.node_type == "chapter" else "chapter"

    project_characters = (
        db.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.updated_at.desc())
        .limit(24)
        .all()
    )
    linked_characters = [link.character for link in node.linked_characters if link.character] if node else []
    context_characters = linked_characters or project_characters[:10]
    world_entries = (
        db.query(WorldbuildingEntry)
        .filter(WorldbuildingEntry.project_id == project_id)
        .order_by(WorldbuildingEntry.dimension.asc(), WorldbuildingEntry.sort_order.asc())
        .limit(18)
        .all()
    )
    sibling_parent_id = node.parent_id if node else None
    sibling_nodes = (
        db.query(OutlineNode)
        .filter(
            OutlineNode.project_id == project_id,
            OutlineNode.parent_id == sibling_parent_id,
            OutlineNode.id != (node.id if node else ""),
        )
        .order_by(OutlineNode.sort_order.asc(), OutlineNode.created_at.asc())
        .limit(30)
        .all()
    )
    recent_nodes = (
        db.query(OutlineNode)
        .filter(OutlineNode.project_id == project_id)
        .order_by(OutlineNode.updated_at.desc())
        .limit(24)
        .all()
    )

    character_context = "\n".join(
        f"- {character.name} ({character.role_type or '未分类'}): "
        f"{(character.personality or character.background or character.appearance or '')[:260]}"
        for character in context_characters
    ) or "暂无角色设定。"
    all_character_names = "、".join(character.name for character in project_characters) or "暂无"
    world_context = "\n".join(
        f"- [{entry.dimension}] {entry.title}: {entry.content[:360]}"
        for entry in world_entries
    ) or "暂无世界观设定。"
    sibling_context = "\n".join(
        f"- [{item.node_type}] {item.title}: {(item.summary or '')[:240]}"
        for item in sibling_nodes
    ) or "暂无同级大纲。"
    recent_context = "\n".join(
        f"- [{item.node_type}] {item.title}: {(item.summary or '')[:180]}"
        for item in recent_nodes
    ) or "暂无近期大纲。"

    target_title = node.title if node else "新大纲节点"
    target_summary = node.summary if node and node.summary else "暂无"
    parent_summary = parent.summary if parent and parent.summary else "暂无"
    messages = [
        {
            "role": "system",
            "content": (
                "你是长篇小说大纲策划助手。你必须参考已有大纲、角色和世界观，"
                "生成接下来连续的章节大纲。每章必须有目标、阻碍、行动、结果、钩子，"
                "并与上一章形成因果推进。只输出合法 JSON，不要 Markdown，不要解释。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"作品标题：{project.title}\n"
                f"作品简介：{project.description or '暂无'}\n"
                f"当前节点：{target_title}\n"
                f"当前节点摘要：{target_summary}\n"
                f"父级摘要：{parent_summary}\n"
                f"作者补充要求：{payload.prompt or '暂无'}\n"
                f"需要连续生成：{suggestion_count} 章\n"
                f"建议节点类型：{fallback_type}\n"
                f"可用角色名称：{all_character_names}\n\n"
                f"相关角色：\n{character_context}\n\n"
                f"世界观设定：\n{world_context}\n\n"
                f"同级大纲参考：\n{sibling_context}\n\n"
                f"近期全局大纲参考：\n{recent_context}\n\n"
                "输出 JSON："
                "{\"suggestions\":[{\"title\":\"章节标题\",\"node_type\":\"chapter|section\","
                "\"summary\":\"150-350字，写清目标、阻碍、行动、结果、钩子\","
                "\"character_names\":[\"角色名\"]}]}\n"
                "硬性要求：suggestions 数量等于需要连续生成的章数；character_names 只能使用可用角色名称；"
                "不要引入与现有大纲、角色、世界观矛盾的新设定。"
            ),
        },
    ]
    result = await LLMGateway.chat_completion(messages=messages, model=payload.model, temperature=0.7)
    content = result.get("content", "")
    suggestions = _parse_outline_ai_suggestions(content, fallback_type, suggestion_count)
    if not suggestions and content.strip():
        suggestions = [{
            "title": target_title if target_title != "新大纲节点" else "新章节",
            "summary": content.strip(),
            "node_type": fallback_type,
            "character_names": [],
        }]
    suggestion = "\n\n".join(f"{item['title']}\n{item['summary']}" for item in suggestions) or content
    return ApiResponse.success(
        data={
            "node_id": payload.node_id,
            "suggestion": suggestion,
            "suggestions": suggestions,
            "model": result.get("model"),
            "usage": result.get("usage"),
        }
    )


@router.post("/projects/{project_id}/outline/ai-suggest-legacy")
async def ai_suggest_outline(
    project_id: str,
    payload: OutlineAISuggestRequest,
    db: Session = Depends(get_db),
):
    """Generate a summary suggestion for an outline node."""
    project = _get_project_or_404(db, project_id)
    node = _get_node_or_404(db, project_id, payload.node_id) if payload.node_id else None
    parent = (
        db.query(OutlineNode)
        .filter(OutlineNode.id == node.parent_id, OutlineNode.project_id == project_id)
        .first()
        if node and node.parent_id
        else None
    )
    linked_characters = [link.character for link in node.linked_characters if link.character] if node else []
    if not linked_characters:
        linked_characters = (
            db.query(Character)
            .filter(Character.project_id == project_id)
            .order_by(Character.updated_at.desc())
            .limit(8)
            .all()
        )
    world_entries = (
        db.query(WorldbuildingEntry)
        .filter(WorldbuildingEntry.project_id == project_id)
        .order_by(WorldbuildingEntry.dimension.asc(), WorldbuildingEntry.sort_order.asc())
        .limit(16)
        .all()
    )
    sibling_nodes = (
        db.query(OutlineNode)
        .filter(
            OutlineNode.project_id == project_id,
            OutlineNode.parent_id == (node.parent_id if node else None),
            OutlineNode.id != (node.id if node else ""),
        )
        .order_by(OutlineNode.sort_order.asc(), OutlineNode.created_at.asc())
        .limit(12)
        .all()
        if node
        else []
    )

    character_context = "\n".join(
        f"- {character.name}（{character.role_type or '未分类'}）: "
        f"{(character.personality or character.background or '')[:240]}"
        for character in linked_characters
    ) or "暂无角色设定。"
    world_context = "\n".join(
        f"- [{entry.dimension}] {entry.title}: {entry.content[:320]}"
        for entry in world_entries
    ) or "暂无世界观设定。"
    sibling_context = "\n".join(
        f"- {NODE_TYPE_LABELS.get(item.node_type, item.node_type)}《{item.title}》: {(item.summary or '')[:220]}"
        for item in sibling_nodes
    ) or "暂无同级节点。"

    target_title = node.title if node else "新大纲节点"
    target_type = NODE_TYPE_LABELS.get(node.node_type, "节点") if node else "节点"
    messages = [
        {
            "role": "system",
            "content": (
                "你是一位资深小说大纲策划编辑，专精于故事结构设计与剧情节奏把控。你深谙三幕结构、英雄之旅、起承转合等多种故事模型，能为任何类型的作品提供专业的大纲建议。\n\n"
                "【任务】\n"
                "根据作品基本信息、角色设定、世界观和同级节点参考，为指定大纲节点生成一段可直接使用的剧情摘要。\n\n"
                "【摘要必须包含】\n"
                "1. 目标：本节点中角色的核心目标或欲望（想达成什么）。\n"
                "2. 阻碍：阻止角色达成目标的主要障碍（外部对抗力量或内部限制）。\n"
                "3. 行动：角色为克服阻碍采取的具体行动。\n"
                "4. 结果：行动产生的直接结果（成功、失败或代价）。\n"
                "5. 钩子：在结果基础上留下的悬念或引出下一节点的线索。\n\n"
                "【质量要求】\n"
                "- 与已有世界观和角色设定严格一致，不得引入矛盾的新设定。\n"
                "- 与父级摘要和同级节点保持逻辑连贯——前一个节点的结果应自然引导到当前节点的开始。\n"
                "- 字数：150-350字，简洁有力，不拖泥带水。\n"
                "- 使用中文输出，强调戏剧性和可写性。\n\n"
                "【禁止事项】\n"
                "- 禁止输出 Markdown 表格、列表或任何格式化标记。\n"
                "- 禁止写「本节点讲述」「本节内容包括」等元描述。\n"
                "- 禁止引入作品中未设定的新角色或新世界观元素。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"作品标题：{project.title}\n"
                f"作品简介：{project.description or '暂无'}\n\n"
                f"目标{target_type}：{target_title}\n"
                f"当前摘要：{node.summary if node and node.summary else '暂无'}\n"
                f"父级摘要：{parent.summary if parent and parent.summary else '暂无'}\n"
                f"作者补充要求：{payload.prompt or '暂无'}\n\n"
                f"相关角色：\n{character_context}\n\n"
                f"世界观设定：\n{world_context}\n\n"
                f"同级节点参考：\n{sibling_context}\n\n"
                "请给出 150-350 字可直接填入大纲摘要的建议。"
            ),
        },
    ]
    result = await LLMGateway.chat_completion(messages=messages, model=payload.model, temperature=0.7)
    return ApiResponse.success(
        data={
            "node_id": payload.node_id,
            "suggestion": result.get("content", ""),
            "model": result.get("model"),
            "usage": result.get("usage"),
        }
    )


@router.put("/projects/{project_id}/outline/{node_id}")
def update_outline_node(
    project_id: str,
    node_id: str,
    payload: OutlineNodeUpdate,
    db: Session = Depends(get_db),
):
    """Update an outline node and its linked characters."""
    _get_project_or_404(db, project_id)
    node = _get_node_or_404(db, project_id, node_id)
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise ValidationError("未提供任何更新字段")

    links = _extract_character_links(update_data.pop("character_ids", None), update_data.pop("characters", None))
    if "parent_id" in update_data:
        _get_parent_or_404(db, project_id, update_data["parent_id"])
        _ensure_no_cycle(db, project_id, node.id, update_data["parent_id"])

    for field, value in update_data.items():
        setattr(node, field, value)
    _replace_character_links(db, project_id, node, links)

    db.commit()
    db.refresh(node)
    return ApiResponse.success(data=_node_to_dict(node), message="大纲节点已更新")


@router.delete("/projects/{project_id}/outline/{node_id}")
def delete_outline_node(project_id: str, node_id: str, db: Session = Depends(get_db)):
    """Delete an outline node and its descendants."""
    _get_project_or_404(db, project_id)
    node = _get_node_or_404(db, project_id, node_id)
    db.delete(node)
    db.commit()
    return ApiResponse.success(message="大纲节点已删除")
