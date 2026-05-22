"""AI Writing Engine — narrator, character dialogue, dialogue battle, text ops, conflict, changes."""
import json
import asyncio
import re
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload

from ..ai.gateway import LLMGateway
from ..core.exceptions import NotFoundError, ValidationError, LLMError
from ..core.response import ApiResponse
from ..database.models import (
    Chapter,
    ChapterCharacter,
    ChapterSnapshot,
    ChapterSummary,
    Character,
    CharacterAIConfig,
    CharacterChangeLog,
    CharacterRelationship,
    CharacterTimeline,
    AssistantConversation,
    AssistantMessage,
    OutlineNode,
    OutlineNodeCharacter,
    Project,
    WorldbuildingEntry,
)
from ..database.session import get_db
from ..schemas.ai_writer import (
    NarratorGenerateRequest,
    CharacterDialogueRequest,
    DialogueBattleRequest,
    RewriteRequest,
    ExpandRequest,
    ContinueRequest,
    ConflictSuggestRequest,
    ConflictAdoptRequest,
    CharacterChangesRequest,
    StoryAssistantRequest,
    AssistantConversationCreate,
    AssistantConversationUpdate,
    AssistantMessageUpdate,
    WorkspaceAssistantRequest,
)

router = APIRouter(tags=["ai-writer"])

DIMENSION_LABELS = {
    "geography": "地理", "history": "历史", "factions": "势力",
    "power_system": "规则体系", "races": "种族", "culture": "文化",
}

STYLE_OPTIONS = ["vivid", "concise", "serious", "humorous", "poetic"]
STYLE_PROMPTS = {
    "vivid": "请用生动形象、富有画面感的语言改写。要求：优先使用具体动作、感官细节和场景调度制造画面感；不要依赖密集比喻或华丽排比；将抽象概括转化为具体场景。",
    "concise": "请用简洁精炼的语言改写，去除冗余。要求：删除重复表述和空洞修饰词；合并可归并的句子；用精准动词和名词替代冗长形容结构；提高信息密度。",
    "serious": "请用严肃庄重的语言改写。要求：句式规整，避免口语化和俏皮话；用词精准克制，不夸张不煽情；保持客观冷静的叙事距离。",
    "humorous": "请用幽默诙谐的语言改写。要求：可运用反讽、夸张、反差、双关等手法；节奏轻快；幽默应为角色和剧情服务，而非单纯搞笑。",
    "poetic": "请用富有诗意的语言改写。要求：注重语句的韵律感和节奏美；善用意象和留白；情感含蓄有层次，避免直白抒情。",
}

DEFAULT_FORBIDDEN_SENTENCE_PATTERNS = "\n".join([
    "不是……是……",
    "不是……而是……",
    "不是……却是……",
    "与其说……不如说……",
])

DEFAULT_RHETORIC_GUIDELINES = (
    "克制使用比喻、拟人、排比等修辞，禁止连续堆叠比喻。"
    "优先用具体动作、感官细节、因果推进和角色反应来表达画面与情绪。"
    "非必要不使用抽象概念比喻；同一段落不要出现多个比喻。"
)

FORBIDDEN_SENTENCE_REGEXES = {
    "不是……是……": [
        r"(?<!是)不是[^。！？!?；;\n]{1,80}[，,、\s]*是[^。！？!?；;\n]{1,80}",
        r"(?<!是)不是[^。！？!?；;\n]{1,80}[。！？!?；;]\s*是[^。！？!?；;\n]{1,80}",
    ],
    "不是……而是……": [
        r"(?<!是)不是[^。！？!?；;\n]{1,120}而是[^。！？!?；;\n]{1,120}",
        r"(?<!是)不是[^。！？!?；;\n]{1,80}[。！？!?；;]\s*而是[^。！？!?；;\n]{1,80}",
    ],
    "不是……却是……": [
        r"(?<!是)不是[^。！？!?；;\n]{1,120}却是[^。！？!?；;\n]{1,120}",
        r"(?<!是)不是[^。！？!?；;\n]{1,80}[。！？!?；;]\s*却是[^。！？!?；;\n]{1,80}",
    ],
    "与其说……不如说……": [
        r"与其说[\s\S]{1,120}?不如说[\s\S]{1,120}?",
    ],
}


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundError("作品不存在")
    return project


def _get_character_or_404(db: Session, project_id: str, character_id: str) -> Character:
    character = (
        db.query(Character)
        .filter(Character.id == character_id, Character.project_id == project_id)
        .first()
    )
    if not character:
        raise NotFoundError("角色不存在")
    return character


def _get_outline_node_or_404(
    db: Session,
    project_id: str,
    outline_node_id: Optional[str],
) -> Optional[OutlineNode]:
    if not outline_node_id:
        return None
    node = (
        db.query(OutlineNode)
        .options(
            selectinload(OutlineNode.linked_characters).selectinload(OutlineNodeCharacter.character)
        )
        .filter(OutlineNode.id == outline_node_id, OutlineNode.project_id == project_id)
        .first()
    )
    if not node:
        raise ValidationError("关联大纲节点必须属于当前作品")
    return node


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------

def _build_world_context(db: Session, project_id: str, outline_node_id: Optional[str] = None) -> str:
    entries = (
        db.query(WorldbuildingEntry)
        .filter(WorldbuildingEntry.project_id == project_id)
        .order_by(WorldbuildingEntry.dimension.asc(), WorldbuildingEntry.sort_order.asc())
        .limit(24)
        .all()
    )
    if not entries:
        return "暂无世界观设定。"
    lines = []
    for entry in entries:
        dim_label = DIMENSION_LABELS.get(entry.dimension, entry.dimension)
        lines.append(f"[{dim_label}] {entry.title}: {entry.content[:400]}")
    return "\n".join(lines)


def _chinese_number_to_int(text: str) -> Optional[int]:
    text = (text or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    digit_map = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    unit_map = {"十": 10, "百": 100, "千": 1000}
    total = 0
    current = 0
    for char in text:
        if char in digit_map:
            current = digit_map[char]
        elif char in unit_map:
            unit = unit_map[char]
            if current == 0:
                current = 1
            total += current * unit
            current = 0
    total += current
    return total or None


def _chapter_order_number(title: str) -> Optional[int]:
    match = re.search(r"第\s*([0-9一二两三四五六七八九十百千万零〇]+)\s*章", title or "")
    if not match:
        match = re.search(r"([0-9]+)", title or "")
    return _chinese_number_to_int(match.group(1)) if match else None


def _build_recent_summaries(db: Session, project_id: str, limit: int = 5) -> str:
    summaries = (
        db.query(ChapterSummary)
        .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
        .filter(Chapter.project_id == project_id)
        .all()
    )
    if not summaries:
        return "暂无前文章节摘要。"
    summaries.sort(
        key=lambda item: (
            _chapter_order_number(item.chapter.title if item.chapter else "") or 0,
            item.chapter.created_at if item.chapter else item.updated_at,
        )
    )
    summaries = summaries[-limit:] if limit else []
    lines = []
    for s in summaries:
        title = s.chapter.title if s.chapter else "未知章节"
        lines.append(f"- {title}: {s.summary_text[:600]}")
    return "\n".join(lines)


def _build_outline_context(db: Session, project_id: str, outline_node_id: Optional[str]) -> str:
    node = _get_outline_node_or_404(db, project_id, outline_node_id)
    if not node:
        return "暂无当前大纲节点。"
    parts = [f"大纲节点：{node.title}（{node.node_type}）[ID: {node.id}]"]
    if node.summary:
        parts.append(f"概要：{node.summary}")
    linked = node.linked_characters
    if linked:
        char_names = [lc.character.name for lc in linked if lc.character]
        parts.append(f"涉及角色：{', '.join(char_names)}")
    return "\n".join(parts)


def _build_scene_characters_context(db: Session, project_id: str, outline_node_id: Optional[str]) -> str:
    if not outline_node_id:
        return ""
    links = (
        db.query(OutlineNodeCharacter)
        .join(OutlineNode, OutlineNode.id == OutlineNodeCharacter.outline_node_id)
        .filter(
            OutlineNodeCharacter.outline_node_id == outline_node_id,
            OutlineNode.project_id == project_id,
        )
        .all()
    )
    if not links:
        return ""
    lines = ["当前场景角色："]
    for link in links:
        char = link.character
        if char:
            role_label = link.role_in_scene or "在场"
            lines.append(
                f"- {char.name}（{char.role_type or '未分类'}，{role_label}）: "
                f"{(char.personality or '')[:200]}"
            )
    return "\n".join(lines)


def _build_character_context(character: Character) -> str:
    parts = [
        f"角色名称：{character.name}",
        f"角色类型：{character.role_type or '未分类'}",
    ]
    if character.appearance:
        parts.append(f"外貌：{character.appearance}")
    if character.personality:
        parts.append(f"性格：{character.personality}")
    if character.background:
        parts.append(f"背景：{character.background}")
    if character.abilities:
        try:
            abilities = json.loads(character.abilities)
            if isinstance(abilities, list) and abilities:
                parts.append(f"能力：{', '.join(abilities)}")
        except (json.JSONDecodeError, TypeError):
            pass
    return "\n".join(parts)


def _build_character_ai_context(character: Character) -> str:
    config = character.ai_config
    if not config:
        return ""
    parts = [f"语气风格：{config.tone_style or 'neutral'}"]
    if config.catchphrases:
        try:
            phrases = json.loads(config.catchphrases)
            if isinstance(phrases, list) and phrases:
                parts.append(f"口头禅：{', '.join(phrases)}")
        except (json.JSONDecodeError, TypeError):
            pass
    parts.append(f"话量偏好：{config.verbosity or 'moderate'}")
    parts.append(f"情感倾向：{config.emotion_tendency or 'neutral'}")
    if config.custom_system_prompt:
        parts.append(f"额外提示：{config.custom_system_prompt}")
    return "\n".join(parts)


def _build_character_relationships(db: Session, project_id: str, character_id: str) -> str:
    rels = (
        db.query(CharacterRelationship)
        .filter(
            CharacterRelationship.project_id == project_id,
            (
                (CharacterRelationship.character_a_id == character_id)
                | (CharacterRelationship.character_b_id == character_id)
            ),
        )
        .all()
    )
    if not rels:
        return "暂无角色关系。"
    lines = []
    for rel in rels:
        other_id = rel.character_b_id if rel.character_a_id == character_id else rel.character_a_id
        other = db.query(Character).filter(Character.id == other_id).first()
        other_name = other.name if other else other_id[:8]
        lines.append(f"- 与{other_name}：{rel.relationship_type}" + (f"（{rel.description}）" if rel.description else ""))
    return "\n".join(lines)


def _build_character_timeline(db: Session, character_id: str, limit: int = 10) -> str:
    events = (
        db.query(CharacterTimeline)
        .filter(CharacterTimeline.character_id == character_id)
        .order_by(CharacterTimeline.created_at.desc())
        .limit(limit)
        .all()
    )
    if not events:
        return "暂无近期经历。"
    lines = ["近期经历："]
    for event in reversed(events):
        emo = f"（情感变化：{event.emotional_state_change}）" if event.emotional_state_change else ""
        lines.append(f"- [{event.event_type}] {event.event_description}{emo}")
    return "\n".join(lines)


def _build_style_context(project: Project) -> str:
    perspective_map = {
        "first_person": "第一人称",
        "third_person": "第三人称",
        "omniscient": "上帝视角",
    }
    style_map = {
        "natural": "自然",
        "vivid": "华丽生动",
        "concise": "白描简洁",
        "serious": "严肃",
        "humorous": "幽默",
        "poetic": "诗意",
    }
    perspective = perspective_map.get(project.narrative_perspective, "第三人称")
    style = style_map.get(project.writing_style, "自然")
    forbidden_patterns = (project.forbidden_sentence_patterns or DEFAULT_FORBIDDEN_SENTENCE_PATTERNS).strip()
    rhetoric_guidelines = (project.rhetoric_guidelines or DEFAULT_RHETORIC_GUIDELINES).strip()
    parts = [f"叙事视角：{perspective}", f"文风偏好：{style}"]
    if forbidden_patterns:
        patterns = [line.strip() for line in forbidden_patterns.splitlines() if line.strip()]
        if patterns:
            parts.append("禁用句式：\n" + "\n".join(f"- {pattern}" for pattern in patterns))
            parts.append("生成或改写时必须主动避开上述句式，包括同义变体和近似模板。")
            parts.append(
                "硬性句式检查：交付前必须自查并改掉所有禁用句式。"
                "跨句变体也禁止，例如“不是A。是B。”、“不是A，而是B。”、“与其说A，不如说B。”。"
            )
    if rhetoric_guidelines:
        parts.append(f"修辞限制：{rhetoric_guidelines}")
    return "\n".join(parts)


def _project_forbidden_patterns(project: Project) -> list[str]:
    raw = (project.forbidden_sentence_patterns or DEFAULT_FORBIDDEN_SENTENCE_PATTERNS).strip()
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _generic_forbidden_regex(pattern: str) -> Optional[str]:
    if "……" not in pattern:
        return None
    pieces = [piece for piece in pattern.split("……") if piece]
    if not pieces:
        return None
    return r"[\s\S]{0,80}?".join(re.escape(piece) for piece in pieces)


def _forbidden_snippet(text: str, start: int, end: int, radius: int = 24) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].replace("\n", "\\n")
    if left > 0:
        snippet = "..." + snippet
    if right < len(text):
        snippet += "..."
    return snippet


def _detect_forbidden_sentence_violations(text: str, project: Project) -> list[dict]:
    if not text:
        return []
    violations: list[dict] = []
    seen: set[tuple[str, int, int]] = set()
    for pattern in _project_forbidden_patterns(project):
        regexes = FORBIDDEN_SENTENCE_REGEXES.get(pattern, [])
        generic = _generic_forbidden_regex(pattern)
        if generic:
            regexes = [*regexes, generic]
        if not regexes and pattern in text:
            start = text.find(pattern)
            regexes = [re.escape(pattern)]
        for regex in regexes:
            for match in re.finditer(regex, text):
                key = (pattern, match.start(), match.end())
                if key in seen:
                    continue
                seen.add(key)
                violations.append({
                    "pattern": pattern,
                    "snippet": _forbidden_snippet(text, match.start(), match.end()),
                    "start": match.start(),
                    "end": match.end(),
                })
                if len(violations) >= 20:
                    return violations
    return violations


def _strip_plain_text_response(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", value)
        value = re.sub(r"\s*```$", "", value).strip()
    return value


def _repair_token_budget(text: str, requested_max_tokens: Optional[int]) -> int:
    estimated = max(2048, int(len(text or "") * 1.8))
    if requested_max_tokens:
        estimated = max(estimated, requested_max_tokens)
    return min(24000, estimated)


def _mechanical_repair_forbidden_sentences(text: str) -> str:
    """Last-resort cleanup for the built-in contrast templates."""

    def clean_tail(value: str) -> str:
        value = value.strip()
        return value[1:] if value.startswith("在") and len(value) > 1 else value

    def replace_not_is(match: re.Match) -> str:
        left = match.group("left").strip()
        right = clean_tail(match.group("right"))
        return f"{left}并非关键，关键在于{right}"

    def replace_rather(match: re.Match) -> str:
        left = match.group("left").strip()
        right = match.group("right").strip()
        return f"{left}这个判断不够准确，{right}更贴近当前情况"

    rules = [
        (
            r"(?<!是)不是(?P<left>[^。！？!?；;\n]{1,80})[，,、\s]*是(?P<right>[^。！？!?；;\n]{1,80})",
            replace_not_is,
        ),
        (
            r"(?<!是)不是(?P<left>[^。！？!?；;\n]{1,80})[。！？!?；;]\s*是(?P<right>[^。！？!?；;\n]{1,80})",
            replace_not_is,
        ),
        (
            r"(?<!是)不是(?P<left>[^。！？!?；;\n]{1,120})而是(?P<right>[^。！？!?；;\n]{1,120})",
            replace_not_is,
        ),
        (
            r"(?<!是)不是(?P<left>[^。！？!?；;\n]{1,120})却是(?P<right>[^。！？!?；;\n]{1,120})",
            replace_not_is,
        ),
        (
            r"与其说(?P<left>[\s\S]{1,120}?)不如说(?P<right>[\s\S]{1,120}?)",
            replace_rather,
        ),
    ]
    repaired = text
    for regex, replacer in rules:
        repaired = re.sub(regex, replacer, repaired)
    return repaired


async def _repair_forbidden_sentence_text(
    text: str,
    project: Project,
    model: Optional[str],
    max_tokens: Optional[int] = None,
) -> tuple[str, list[dict], list[dict]]:
    """Rewrite text only when it violates project-level forbidden sentence rules."""
    before = _detect_forbidden_sentence_violations(text, project)
    if not before:
        return text, [], []

    repaired = text
    remaining = before
    patterns = _project_forbidden_patterns(project)
    for _attempt in range(2):
        hit_list = "\n".join(
            f"- {item['pattern']}：{item['snippet']}" for item in remaining[:12]
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是小说正文句式审校器。你的任务只做一件事："
                    "在不改变剧情事实、角色行动、信息顺序、叙事视角和语气的前提下，"
                    "删除或改写命中的禁用句式。"
                    "不要解释，不要加标题，不要输出清单，只输出修订后的完整正文。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "禁用句式如下，包含跨句变体也禁止：\n"
                    + "\n".join(f"- {pattern}" for pattern in patterns)
                    + "\n\n已经命中的片段：\n"
                    + hit_list
                    + "\n\n请修订下面全文。要求：保留原有剧情、人物、设定和段落顺序；"
                    "只把命中的句式改成普通因果、递进或判断句；避免大量比喻。\n\n"
                    f"{repaired}"
                ),
            },
        ]
        result = await LLMGateway.chat_completion(
            messages=messages,
            model=model,
            temperature=0.1,
            max_tokens=_repair_token_budget(repaired, max_tokens),
            retry=1,
        )
        candidate = _strip_plain_text_response(result.get("content", ""))
        if candidate:
            repaired = candidate
        remaining = _detect_forbidden_sentence_violations(repaired, project)
        if not remaining:
            break
    if remaining:
        repaired = _mechanical_repair_forbidden_sentences(repaired)
        remaining = _detect_forbidden_sentence_violations(repaired, project)
    return repaired, before, remaining


async def _repair_assistant_parsed_style(
    parsed: dict,
    project: Project,
    model: Optional[str],
    max_tokens: Optional[int] = None,
) -> list[dict]:
    """Repair visible assistant reply and generated chapter draft fields in-place."""
    reports: list[dict] = []

    async def repair_field(owner: dict, key: str, field_name: str) -> None:
        value = str(owner.get(key) or "")
        if not value.strip():
            return
        repaired, before, remaining = await _repair_forbidden_sentence_text(value, project, model, max_tokens)
        if before:
            owner[key] = repaired
            reports.append({
                "field": field_name,
                "fixed": not remaining,
                "violations": before[:8],
                "remaining": remaining[:8],
            })

    await repair_field(parsed, "reply", "reply")
    draft = parsed.get("chapter_draft")
    if isinstance(draft, dict):
        await repair_field(draft, "content", "chapter_draft.content")
        await repair_field(draft, "summary", "chapter_draft.summary")
    return reports


def _count_words(text: str) -> int:
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", text or "")
    without_cjk = re.sub(r"[\u4e00-\u9fff]", " ", text or "")
    latin_words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", without_cjk)
    return len(cjk_chars) + len(latin_words)


def _strip_json_fences(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```json"):
        value = value[7:]
    elif value.startswith("```"):
        value = value[3:]
    if value.endswith("```"):
        value = value[:-3]
    return value.strip()


def _parse_json_object(text: str) -> Optional[dict]:
    cleaned = _strip_json_fences(text)
    candidates = [cleaned]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        candidates.append(cleaned[start:end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            continue
    return None


def _build_outline_overview(db: Session, project_id: str, limit: int = 60) -> str:
    nodes = (
        db.query(OutlineNode)
        .filter(OutlineNode.project_id == project_id)
        .order_by(OutlineNode.sort_order.asc(), OutlineNode.created_at.asc())
        .limit(limit)
        .all()
    )
    if not nodes:
        return "暂无大纲。"
    node_by_id = {node.id: node for node in nodes}

    def path_for(node: OutlineNode) -> str:
        titles = [node.title]
        parent = node_by_id.get(node.parent_id) if node.parent_id else None
        visited = {node.id}
        while parent and parent.id not in visited:
            visited.add(parent.id)
            titles.append(parent.title)
            parent = node_by_id.get(parent.parent_id) if parent.parent_id else None
        return " / ".join(reversed(titles))

    lines = []
    for node in nodes:
        summary = f"：{node.summary[:220]}" if node.summary else ""
        lines.append(f"- [{node.id}] {path_for(node)}（{node.node_type}，{node.status or 'pending'}）{summary}")
    return "\n".join(lines)


def _build_character_catalog(db: Session, project_id: str, limit: int = 30) -> str:
    characters = (
        db.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.role_type.asc(), Character.updated_at.desc())
        .limit(limit)
        .all()
    )
    if not characters:
        return "暂无角色档案。"
    lines = []
    for character in characters:
        parts = [
            f"- {character.name}（{character.role_type or '未分类'}）",
            (character.personality or "")[:180],
        ]
        if character.background:
            parts.append(f"背景：{character.background[:180]}")
        if character.appearance:
            parts.append(f"外貌：{character.appearance[:120]}")
        lines.append("；".join(part for part in parts if part))
    return "\n".join(lines)


def _build_relationship_context(db: Session, project_id: str, limit: int = 50) -> str:
    rels = (
        db.query(CharacterRelationship)
        .filter(CharacterRelationship.project_id == project_id)
        .order_by(CharacterRelationship.created_at.asc())
        .limit(limit)
        .all()
    )
    if not rels:
        return "暂无角色关系。"
    characters = {
        character.id: character.name
        for character in db.query(Character).filter(Character.project_id == project_id).all()
    }
    lines = []
    for rel in rels:
        a = characters.get(rel.character_a_id, rel.character_a_id[:8])
        b = characters.get(rel.character_b_id, rel.character_b_id[:8])
        detail = f"：{rel.description[:220]}" if rel.description else ""
        lines.append(f"- {a} -> {b}：{rel.relationship_type}{detail}")
    return "\n".join(lines)


def _build_chapter_detail_context(
    db: Session,
    project_id: str,
    chapter_id: Optional[str],
    max_chars: int = 12000,
) -> str:
    query = db.query(Chapter).filter(Chapter.project_id == project_id)
    chapter = query.filter(Chapter.id == chapter_id).first() if chapter_id else None
    if not chapter:
        chapter = query.order_by(Chapter.created_at.desc()).first()
    if not chapter:
        return "暂无章节正文。"
    content = chapter.content or ""
    if len(content) > max_chars:
        content = content[:max_chars] + "\n……（后续正文已截断）"
    return f"章节：{chapter.title}\n字数：{chapter.word_count or _count_words(chapter.content or '')}\n正文：\n{content}"


def _ordered_project_chapters(db: Session, project_id: str) -> list[Chapter]:
    chapters = db.query(Chapter).filter(Chapter.project_id == project_id).all()
    chapters.sort(
        key=lambda item: (
            _chapter_order_number(item.title) or 0,
            item.created_at,
        )
    )
    return chapters


def _build_recent_chapter_details(
    db: Session,
    project_id: str,
    limit: int = 8,
    max_chars_each: int = 2200,
) -> str:
    chapters = _ordered_project_chapters(db, project_id)
    if not chapters:
        return "暂无章节正文。"
    sections = []
    for chapter in chapters[-limit:]:
        content = chapter.content or ""
        if len(content) > max_chars_each:
            content = content[:max_chars_each] + "\n……（本章后续正文已截断）"
        summary = chapter.summary.summary_text if chapter.summary else ""
        sections.append(
            f"【{chapter.title}】\n"
            f"摘要：{summary[:800] if summary else '暂无'}\n"
            f"正文片段：\n{content}"
        )
    return "\n\n".join(sections)


def _assistant_heuristic_plan(message: str) -> dict:
    text = message.lower()
    tools = {"read_recent_summaries", "read_outline", "read_worldbuilding", "read_characters", "read_relationships"}
    if any(key in text for key in ["矛盾", "冲突", "合理", "检查", "详细", "正文", "bug", "不一致"]):
        tools.add("read_chapter_detail")
    if any(key in text for key in ["写", "生成", "新章节", "创建章节", "对话", "扮演", "行动", "出场"]):
        tools.add("roleplay_characters")
    should_create = bool(
        any(key in text for key in ["创建章节", "新章节", "直接生成章节", "写一章", "写第", "帮我写第"])
        or re.search(r"写\s*第?\s*\d+\s*章", text)
        or re.search(r"第\s*\d+\s*章", text) and any(key in text for key in ["写", "生成", "创建"])
    )
    return {
        "intent": "write" if should_create else "advise",
        "tools": sorted(tools),
        "character_names": [],
        "needs_worldbuilding": any(key in text for key in ["设定", "世界观", "规则", "势力", "地图"]),
        "should_create_chapter": should_create,
        "chapter_title": _chapter_title_from_request(message) if should_create else "",
        "reason": "启发式计划",
    }


def _chapter_title_from_request(message: str) -> str:
    text = (message or "").strip()
    match = re.search(r"第\s*([0-9一二两三四五六七八九十百千万零〇]+)\s*章", text)
    if match:
        return f"第{match.group(1)}章"
    return "AI生成章节"


def _normalize_assistant_plan(raw_plan: Optional[dict], message: str) -> dict:
    fallback = _assistant_heuristic_plan(message)
    if not raw_plan:
        return fallback
    allowed_tools = {
        "read_recent_summaries",
        "read_outline",
        "read_worldbuilding",
        "read_characters",
        "read_relationships",
        "read_chapter_detail",
        "roleplay_characters",
    }
    tools = [tool for tool in raw_plan.get("tools") or [] if tool in allowed_tools]
    for tool in fallback["tools"]:
        if tool not in tools:
            tools.append(tool)
    names = [
        str(name).strip()
        for name in raw_plan.get("character_names") or []
        if str(name).strip()
    ][:6]
    return {
        "intent": str(raw_plan.get("intent") or fallback["intent"])[:50],
        "tools": tools,
        "character_names": names,
        "needs_worldbuilding": bool(raw_plan.get("needs_worldbuilding", fallback["needs_worldbuilding"])),
        "should_create_chapter": bool(raw_plan.get("should_create_chapter")) or bool(fallback["should_create_chapter"]),
        "chapter_title": str(raw_plan.get("chapter_title") or fallback.get("chapter_title") or _chapter_title_from_request(message) or "")[:200],
        "reason": str(raw_plan.get("reason") or fallback["reason"])[:500],
    }


def _resolve_assistant_characters(
    db: Session,
    project_id: str,
    names: list[str],
    outline_node_id: Optional[str],
    limit: int = 4,
) -> list[Character]:
    resolved: list[Character] = []
    seen: set[str] = set()
    clean_names = {name.strip() for name in names if name.strip()}
    if clean_names:
        characters = (
            db.query(Character)
            .filter(Character.project_id == project_id, Character.name.in_(clean_names))
            .all()
        )
        for character in characters:
            resolved.append(character)
            seen.add(character.id)
    if outline_node_id and len(resolved) < limit:
        links = (
            db.query(OutlineNodeCharacter)
            .join(OutlineNode, OutlineNode.id == OutlineNodeCharacter.outline_node_id)
            .filter(OutlineNode.project_id == project_id, OutlineNodeCharacter.outline_node_id == outline_node_id)
            .all()
        )
        for link in links:
            if link.character and link.character.id not in seen:
                resolved.append(link.character)
                seen.add(link.character.id)
            if len(resolved) >= limit:
                break
    if len(resolved) < limit:
        extras = (
            db.query(Character)
            .filter(Character.project_id == project_id)
            .order_by(Character.role_type.asc(), Character.updated_at.desc())
            .limit(limit * 2)
            .all()
        )
        for character in extras:
            if character.id not in seen:
                resolved.append(character)
                seen.add(character.id)
            if len(resolved) >= limit:
                break
    return resolved[:limit]


async def _assistant_character_roleplay(
    db: Session,
    project_id: str,
    character: Character,
    user_message: str,
    outline_ctx: str,
    summaries: str,
    model: Optional[str],
) -> dict:
    project = _get_project_or_404(db, project_id)
    messages = [
        {
            "role": "system",
            "content": (
                f"你是小说角色「{character.name}」的角色AI。\n"
                "请根据角色档案、关系和当前剧情判断这个角色是否会主动行动或发言。"
                "只输出JSON，不要输出解释性散文。\n"
                "格式：{\"should_act\":true,\"action_type\":\"dialogue|action|inner|none\",\"content\":\"角色会说/做/想的内容\",\"rationale\":\"为什么符合人设\"}\n\n"
                f"【角色档案】\n{_build_character_context(character)}\n\n"
                f"【角色AI设定】\n{_build_character_ai_context(character)}\n\n"
                f"【关系网】\n{_build_character_relationships(db, project_id, character.id)}\n\n"
                f"【近期经历】\n{_build_character_timeline(db, character.id)}\n\n"
                f"【作品文风约束】\n{_build_style_context(project)}\n\n"
                f"【当前大纲】\n{outline_ctx}\n\n"
                f"【前文摘要】\n{summaries}"
            ),
        },
        {"role": "user", "content": user_message},
    ]
    result = await LLMGateway.chat_completion(messages=messages, model=model, temperature=0.6, max_tokens=1200)
    parsed = _parse_json_object(result.get("content", ""))
    if not parsed:
        parsed = {
            "should_act": False,
            "action_type": "none",
            "content": "",
            "rationale": result.get("content", "")[:500],
        }
    return {
        "character_id": character.id,
        "character_name": character.name,
        "should_act": bool(parsed.get("should_act")),
        "action_type": str(parsed.get("action_type") or "none")[:50],
        "content": str(parsed.get("content") or "")[:4000],
        "rationale": str(parsed.get("rationale") or "")[:1000],
    }


def _create_assistant_chapter(
    db: Session,
    project_id: str,
    title: str,
    content: str,
    outline_node_id: Optional[str],
    summary_text: str,
    involved_character_names: list[str],
    model: Optional[str],
) -> Optional[Chapter]:
    title = (title or "").strip()[:200]
    content = (content or "").strip()
    if not title or not content:
        return None
    outline_node = _get_outline_node_or_404(db, project_id, outline_node_id)
    chapter = Chapter(
        project_id=project_id,
        outline_node_id=outline_node.id if outline_node else None,
        title=title,
        content=content,
        word_count=_count_words(content),
        current_version=1,
    )
    db.add(chapter)
    db.flush()
    db.add(ChapterSummary(
        chapter_id=chapter.id,
        summary_text=(summary_text or title)[:20000],
        key_events=None,
        token_count=len(summary_text or title),
        ai_model=model,
    ))
    names = {name.strip() for name in involved_character_names if name and name.strip()}
    if names:
        characters = (
            db.query(Character)
            .filter(Character.project_id == project_id, Character.name.in_(names))
            .all()
        )
        for character in characters:
            db.add(ChapterCharacter(
                chapter_id=chapter.id,
                character_id=character.id,
                appearance_type="AI助手识别",
                description="由自动写作助手创建章节时关联",
            ))
    return chapter


def _chapter_brief(chapter: Chapter) -> dict:
    return {
        "id": chapter.id,
        "title": chapter.title,
        "outline_node_id": chapter.outline_node_id,
        "word_count": chapter.word_count or 0,
    }


def _create_assistant_chapter_placeholder(
    db: Session,
    project_id: str,
    title: str,
    outline_node_id: Optional[str],
) -> Chapter:
    outline_node = _get_outline_node_or_404(db, project_id, outline_node_id)
    clean_title = (title or "AI生成章节").strip()[:200] or "AI生成章节"
    chapter = Chapter(
        project_id=project_id,
        outline_node_id=outline_node.id if outline_node else None,
        title=clean_title,
        content="（AI正在生成正文，完成后会自动写入。）",
        word_count=0,
        current_version=1,
    )
    db.add(chapter)
    db.flush()
    return chapter


def _finalize_assistant_chapter(
    db: Session,
    chapter: Chapter,
    title: str,
    content: str,
    summary_text: str,
    involved_character_names: list[str],
    model: Optional[str],
) -> Chapter:
    clean_title = (title or chapter.title or "AI生成章节").strip()[:200] or "AI生成章节"
    clean_content = (content or "").strip()
    chapter.title = clean_title
    chapter.content = clean_content
    chapter.word_count = _count_words(clean_content)
    chapter.current_version = max(1, chapter.current_version or 1) + 1
    chapter.updated_at = datetime.utcnow()
    db.add(ChapterSnapshot(
        chapter_id=chapter.id,
        version_number=chapter.current_version,
        content=clean_content,
        word_count=chapter.word_count,
        trigger_type="ai_insert",
    ))

    if chapter.summary:
        chapter.summary.summary_text = (summary_text or clean_title)[:20000]
        chapter.summary.key_events = None
        chapter.summary.token_count = len(summary_text or clean_title)
        chapter.summary.ai_model = model
        chapter.summary.updated_at = datetime.utcnow()
    else:
        db.add(ChapterSummary(
            chapter_id=chapter.id,
            summary_text=(summary_text or clean_title)[:20000],
            key_events=None,
            token_count=len(summary_text or clean_title),
            ai_model=model,
        ))

    names = {name.strip() for name in involved_character_names if name and name.strip()}
    if names:
        db.query(ChapterCharacter).filter(ChapterCharacter.chapter_id == chapter.id).delete()
        characters = (
            db.query(Character)
            .filter(Character.project_id == chapter.project_id, Character.name.in_(names))
            .all()
        )
        for character in characters:
            db.add(ChapterCharacter(
                chapter_id=chapter.id,
                character_id=character.id,
                appearance_type="AI助手识别",
                description="由自动写作助手创建章节时关联",
            ))
    return chapter


def _assistant_history_text(history: list[dict], limit: int = 8) -> str:
    lines = []
    for item in (history or [])[-limit:]:
        if not isinstance(item, dict):
            continue
        role = "用户" if item.get("role") == "user" else "助手"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}：{content[:6000]}")
    return "\n\n".join(lines) or "暂无对话历史。"


def _assistant_conversation_to_dict(conversation: AssistantConversation, message_count: Optional[int] = None) -> dict:
    return {
        "id": conversation.id,
        "project_id": conversation.project_id,
        "title": conversation.title,
        "scope": conversation.scope,
        "current_chapter_id": conversation.current_chapter_id,
        "current_outline_node_id": conversation.current_outline_node_id,
        "model": conversation.model,
        "message_count": message_count,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }


def _assistant_message_to_dict(message: AssistantMessage) -> dict:
    payload = None
    if message.payload_json:
        try:
            payload = json.loads(message.payload_json)
        except Exception:
            payload = None
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "role": message.role,
        "content": message.content,
        "payload": payload,
        "status": message.status,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "updated_at": message.updated_at.isoformat() if message.updated_at else None,
    }


def _get_assistant_conversation_or_404(
    db: Session,
    project_id: str,
    conversation_id: str,
) -> AssistantConversation:
    conversation = (
        db.query(AssistantConversation)
        .filter(
            AssistantConversation.id == conversation_id,
            AssistantConversation.project_id == project_id,
        )
        .first()
    )
    if not conversation:
        raise NotFoundError("助手对话不存在")
    return conversation


def _assistant_history_from_messages(
    db: Session,
    conversation_id: str,
    before_message_id: Optional[str] = None,
    limit: int = 8,
) -> str:
    messages = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.conversation_id == conversation_id)
        .order_by(
            AssistantMessage.created_at.asc(),
            AssistantMessage.role.desc(),
            AssistantMessage.updated_at.asc(),
            AssistantMessage.id.asc(),
        )
        .all()
    )
    history: list[dict] = []
    for message in messages:
        if before_message_id and message.id == before_message_id:
            break
        if message.status not in {"completed", "running"}:
            continue
        history.append({"role": message.role, "content": message.content})
    return _assistant_history_text(history, limit=limit)


def _assistant_title_from_message(message: str) -> str:
    title = " ".join((message or "").strip().split())
    if not title:
        return "新对话"
    return title[:36] + ("..." if len(title) > 36 else "")


def _character_payload(character: Character) -> dict:
    abilities: list[str] = []
    if character.abilities:
        try:
            parsed = json.loads(character.abilities)
            abilities = parsed if isinstance(parsed, list) else []
        except Exception:
            abilities = [part.strip() for part in character.abilities.split(",") if part.strip()]
    return {
        "id": character.id,
        "name": character.name,
        "appearance": character.appearance,
        "personality": character.personality,
        "background": character.background,
        "abilities": abilities,
        "role_type": character.role_type,
        "current_version": character.current_version,
    }


def _outline_node_payload(node: OutlineNode) -> dict:
    return {
        "id": node.id,
        "parent_id": node.parent_id,
        "node_type": node.node_type,
        "title": node.title,
        "summary": node.summary,
        "status": node.status,
        "sort_order": node.sort_order,
        "linked_characters": [
            {"id": link.character.id, "name": link.character.name, "role_in_scene": link.role_in_scene}
            for link in node.linked_characters
            if link.character
        ],
    }


WORLD_DIMENSIONS = {"geography", "history", "factions", "power_system", "races", "culture"}


def _worldbuilding_payload(entry: WorldbuildingEntry) -> dict:
    return {
        "id": entry.id,
        "dimension": entry.dimension,
        "title": entry.title,
        "content": entry.content,
        "sort_order": entry.sort_order,
    }


def _find_worldbuilding_by_title_or_id(db: Session, project_id: str, value: object) -> Optional[WorldbuildingEntry]:
    text = str(value or "").strip()
    if not text:
        return None
    return (
        db.query(WorldbuildingEntry)
        .filter(WorldbuildingEntry.project_id == project_id)
        .filter((WorldbuildingEntry.id == text) | (WorldbuildingEntry.title == text))
        .first()
    )


def _find_character_by_name_or_id(db: Session, project_id: str, value: object) -> Optional[Character]:
    text = str(value or "").strip()
    if not text:
        return None
    return (
        db.query(Character)
        .filter(Character.project_id == project_id)
        .filter((Character.id == text) | (Character.name == text))
        .first()
    )


def _normalize_outline_lookup(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[\s:：,，.。;；!！?？()（）【】\[\]《》<>\"'“”‘’_-]+", "", text)


def _find_outline_by_title_or_id(db: Session, project_id: str, value: object) -> Optional[OutlineNode]:
    text = str(value or "").strip()
    if not text:
        return None
    base_query = (
        db.query(OutlineNode)
        .options(selectinload(OutlineNode.linked_characters).selectinload(OutlineNodeCharacter.character))
        .filter(OutlineNode.project_id == project_id)
    )
    exact = (
        base_query
        .filter((OutlineNode.id == text) | (OutlineNode.title == text))
        .order_by(OutlineNode.updated_at.desc())
        .first()
    )
    if exact:
        return exact
    normalized = _normalize_outline_lookup(text)
    if not normalized:
        return None
    candidates = (
        base_query
        .order_by(OutlineNode.updated_at.desc(), OutlineNode.sort_order.desc())
        .all()
    )
    for node in candidates:
        if _normalize_outline_lookup(node.title) == normalized:
            return node
    for node in candidates:
        node_title = _normalize_outline_lookup(node.title)
        if node_title and (normalized in node_title or node_title in normalized):
            return node
    return None


def _character_ids_from_names(db: Session, project_id: str, names: object) -> list[str]:
    if not isinstance(names, list):
        return []
    ids = []
    for name in names:
        character = _find_character_by_name_or_id(db, project_id, name)
        if character and character.id not in ids:
            ids.append(character.id)
    return ids


def _replace_outline_links_by_names(db: Session, project_id: str, node: OutlineNode, names: object) -> None:
    ids = _character_ids_from_names(db, project_id, names)
    if not ids:
        return
    node.linked_characters.clear()
    db.flush()
    for character_id in ids:
        node.linked_characters.append(OutlineNodeCharacter(character_id=character_id, role_in_scene="AI关联"))


def _next_outline_sort_order(db: Session, project_id: str, parent_id: Optional[str]) -> int:
    last = (
        db.query(OutlineNode)
        .filter(OutlineNode.project_id == project_id, OutlineNode.parent_id == parent_id)
        .order_by(OutlineNode.sort_order.desc(), OutlineNode.created_at.desc())
        .first()
    )
    return (last.sort_order + 1) if last and last.sort_order is not None else 0


def _next_worldbuilding_sort_order(db: Session, project_id: str, dimension: str) -> int:
    last = (
        db.query(WorldbuildingEntry)
        .filter(WorldbuildingEntry.project_id == project_id, WorldbuildingEntry.dimension == dimension)
        .order_by(WorldbuildingEntry.sort_order.desc(), WorldbuildingEntry.created_at.desc())
        .first()
    )
    return (last.sort_order + 1) if last and last.sort_order is not None else 0


def _execute_workspace_action(db: Session, project_id: str, action: dict) -> dict:
    tool = str(action.get("tool") or "").strip()
    args = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
    if not tool:
        return {"tool": "unknown", "status": "skipped", "detail": "工具名为空"}

    if tool == "create_outline_node":
        parent_id = str(args.get("parent_id") or "").strip() or None
        parent_warning = ""
        if parent_id:
            parent = _find_outline_by_title_or_id(db, project_id, parent_id)
            if parent:
                parent_id = parent.id
            else:
                parent_id = None
                parent_warning = "；未找到当前作品内的父级大纲，已作为根节点创建"
        node_type = str(args.get("node_type") or "chapter")
        if node_type not in {"volume", "chapter", "section"}:
            node_type = "chapter"
        title = str(args.get("title") or "").strip()
        summary = str(args.get("summary") or "").strip()
        if not title:
            return {"tool": tool, "status": "skipped", "detail": "标题为空"}
        node = OutlineNode(
            project_id=project_id,
            parent_id=parent_id,
            node_type=node_type,
            title=title[:200],
            summary=summary,
            status=str(args.get("status") or "pending"),
            sort_order=int(args.get("sort_order") if args.get("sort_order") is not None else _next_outline_sort_order(db, project_id, parent_id)),
        )
        db.add(node)
        db.flush()
        _replace_outline_links_by_names(db, project_id, node, args.get("character_names"))
        return {"tool": tool, "status": "ok", "detail": f"已创建大纲：{node.title}{parent_warning}", "data": _outline_node_payload(node)}

    if tool == "update_outline_node":
        node_ref = (
            args.get("id")
            or args.get("node_id")
            or args.get("outline_node_id")
            or args.get("current_title")
            or args.get("old_title")
            or args.get("outline_node_title")
            or args.get("title")
        )
        node = _find_outline_by_title_or_id(db, project_id, node_ref)
        if not node and args.get("title"):
            node = _find_outline_by_title_or_id(db, project_id, args.get("title"))
        if not node:
            return {"tool": tool, "status": "skipped", "detail": "未找到当前作品内的大纲节点"}
        if args.get("title"):
            node.title = str(args.get("title")).strip()[:200]
        if "summary" in args:
            node.summary = str(args.get("summary") or "")
        if args.get("status") in {"pending", "in_progress", "completed"}:
            node.status = str(args.get("status"))
        if args.get("node_type") in {"volume", "chapter", "section"}:
            node.node_type = str(args.get("node_type"))
        if "character_names" in args:
            _replace_outline_links_by_names(db, project_id, node, args.get("character_names"))
        node.updated_at = datetime.utcnow()
        return {"tool": tool, "status": "ok", "detail": f"已更新大纲：{node.title}", "data": _outline_node_payload(node)}

    if tool == "create_character":
        name = str(args.get("name") or "").strip()
        if not name:
            return {"tool": tool, "status": "skipped", "detail": "角色名为空"}
        character = Character(
            project_id=project_id,
            name=name[:100],
            appearance=str(args.get("appearance") or "")[:4000],
            personality=str(args.get("personality") or "")[:4000],
            background=str(args.get("background") or "")[:8000],
            abilities=json.dumps(args.get("abilities") if isinstance(args.get("abilities"), list) else [], ensure_ascii=False),
            role_type=str(args.get("role_type") or "supporting"),
            is_evolution_tracked=True,
        )
        db.add(character)
        db.flush()
        return {"tool": tool, "status": "ok", "detail": f"已创建角色：{character.name}", "data": _character_payload(character)}

    if tool == "update_character":
        character = _find_character_by_name_or_id(db, project_id, args.get("id") or args.get("name"))
        if not character:
            return {"tool": tool, "status": "skipped", "detail": "未找到角色"}
        changed = False
        for field, limit in [("appearance", 4000), ("personality", 4000), ("background", 8000), ("role_type", 100)]:
            if field in args:
                setattr(character, field, str(args.get(field) or "")[:limit])
                changed = True
        if "abilities" in args and isinstance(args.get("abilities"), list):
            character.abilities = json.dumps(args.get("abilities"), ensure_ascii=False)
            changed = True
        if changed:
            character.current_version = (character.current_version or 1) + 1
            character.updated_at = datetime.utcnow()
            db.add(CharacterVersion(
                character_id=character.id,
                version_number=character.current_version,
                snapshot_data=json.dumps(_character_payload(character), ensure_ascii=False),
                change_summary="AI助手调整角色档案",
            ))
        return {"tool": tool, "status": "ok", "detail": f"已更新角色：{character.name}", "data": _character_payload(character)}

    if tool == "create_relationship":
        source = _find_character_by_name_or_id(db, project_id, args.get("source") or args.get("from"))
        target = _find_character_by_name_or_id(db, project_id, args.get("target") or args.get("to"))
        if not source or not target or source.id == target.id:
            return {"tool": tool, "status": "skipped", "detail": "关系角色无效"}
        rel = CharacterRelationship(
            project_id=project_id,
            character_a_id=source.id,
            character_b_id=target.id,
            relationship_type=str(args.get("relationship_type") or "关联")[:100],
            description=str(args.get("description") or "")[:4000],
        )
        db.add(rel)
        db.flush()
        return {"tool": tool, "status": "ok", "detail": f"已创建关系：{source.name} - {target.name}"}

    if tool == "create_worldbuilding_entry":
        dimension = str(args.get("dimension") or "culture").strip()
        if dimension not in WORLD_DIMENSIONS:
            dimension = "culture"
        title = str(args.get("title") or "").strip()
        content = str(args.get("content") or "").strip()
        if not title or not content:
            return {"tool": tool, "status": "skipped", "detail": "世界观标题或内容为空"}
        if args.get("related_characters") or args.get("plot_usage") or args.get("constraints"):
            extras = []
            related = args.get("related_characters")
            constraints = args.get("constraints")
            if isinstance(related, list) and related:
                extras.append("关联角色：" + "、".join(str(item) for item in related if item))
            if args.get("plot_usage"):
                extras.append("剧情用途：" + str(args.get("plot_usage")))
            if isinstance(constraints, list) and constraints:
                extras.append("限制条件：" + "；".join(str(item) for item in constraints if item))
            if extras:
                content = f"{content}\n\n" + "\n".join(extras)
        entry = WorldbuildingEntry(
            project_id=project_id,
            dimension=dimension,
            title=title[:200],
            content=content[:12000],
            sort_order=int(args.get("sort_order") if args.get("sort_order") is not None else _next_worldbuilding_sort_order(db, project_id, dimension)),
        )
        db.add(entry)
        db.flush()
        return {"tool": tool, "status": "ok", "detail": f"已创建世界观：{entry.title}", "data": _worldbuilding_payload(entry)}

    if tool == "update_worldbuilding_entry":
        entry = _find_worldbuilding_by_title_or_id(db, project_id, args.get("id") or args.get("title"))
        if not entry:
            return {"tool": tool, "status": "skipped", "detail": "未找到世界观条目"}
        if args.get("dimension") in WORLD_DIMENSIONS:
            entry.dimension = str(args.get("dimension"))
        if args.get("title"):
            entry.title = str(args.get("title")).strip()[:200]
        if "content" in args:
            entry.content = str(args.get("content") or "")[:12000]
        if args.get("sort_order") is not None:
            entry.sort_order = int(args.get("sort_order"))
        entry.updated_at = datetime.utcnow()
        return {"tool": tool, "status": "ok", "detail": f"已更新世界观：{entry.title}", "data": _worldbuilding_payload(entry)}

    if tool == "create_chapter":
        title = str(args.get("title") or "").strip()
        content = str(args.get("content") or "")
        if not title or not content.strip():
            return {"tool": tool, "status": "skipped", "detail": "章节标题或正文为空"}
        outline_node = None
        for ref in (args.get("outline_node_id"), args.get("outline_node_title"), args.get("outline_title")):
            outline_node = _find_outline_by_title_or_id(db, project_id, ref)
            if outline_node:
                break
        outline_node_id = outline_node.id if outline_node else None
        chapter = _create_assistant_chapter(
            db,
            project_id,
            title[:200],
            content,
            outline_node_id,
            str(args.get("summary") or ""),
            [str(name) for name in (args.get("involved_characters") or []) if name] if isinstance(args.get("involved_characters"), list) else [],
            str(args.get("model") or "") or None,
        )
        if not chapter:
            return {"tool": tool, "status": "skipped", "detail": "章节创建失败"}
        return {"tool": tool, "status": "ok", "detail": f"已创建章节：{chapter.title}", "data": {"id": chapter.id, "title": chapter.title}}

    return {"tool": tool, "status": "skipped", "detail": "未知工具"}


def _is_affirmative_confirmation(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    if any(phrase in normalized for phrase in ["不是", "不行", "不要", "不按", "不可以", "否", "换个方向", "改一下"]):
        return False
    return any(
        phrase in normalized
        for phrase in [
            "是",
            "可以",
            "确认",
            "同意",
            "按这个",
            "就这样",
            "继续",
            "没问题",
            "照这个",
            "就按",
            "yes",
            "ok",
        ]
    ) or normalized in {"好", "好的", "行"}


def _user_requests_chapter_creation(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    return any(
        phrase in normalized
        for phrase in ["写第", "写一章", "写新章", "新章节", "创建章节", "生成章节", "帮我写", "开始写", "续写第"]
    )


def _chapter_action_needs_outline_confirmation(
    db: Session,
    project_id: str,
    actions: list[dict],
    user_message: str,
) -> bool:
    confirmed = _is_affirmative_confirmation(user_message)
    pending_outline_titles = set()
    for action in actions:
        if isinstance(action, dict) and action.get("tool") == "create_outline_node":
            args = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
            title = str(args.get("title") or "").strip()
            if title:
                pending_outline_titles.add(title)
    if pending_outline_titles and _user_requests_chapter_creation(user_message) and not confirmed:
        return True
    for action in actions:
        if not isinstance(action, dict) or action.get("tool") != "create_chapter":
            continue
        args = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
        outline_ref = args.get("outline_node_id") or args.get("outline_node_title") or args.get("outline_title")
        if _find_outline_by_title_or_id(db, project_id, outline_ref):
            continue
        if confirmed and str(outline_ref or "").strip() in pending_outline_titles:
            continue
        if confirmed and len(pending_outline_titles) == 1 and not str(outline_ref or "").strip():
            args["outline_node_title"] = next(iter(pending_outline_titles))
            continue
        if not confirmed:
            return True
        return True
    return False


# ---------------------------------------------------------------------------
# SSE streaming helper
# ---------------------------------------------------------------------------

async def _sse_writer_stream(
    generator: AsyncGenerator[str, None],
    project: Optional[Project] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    full_text = ""
    try:
        async for chunk in generator:
            full_text += chunk
            data = json.dumps({"type": "token", "content": chunk}, ensure_ascii=False, separators=(",", ":"))
            yield f"data: {data}\n\n"
        if project:
            violations = _detect_forbidden_sentence_violations(full_text, project)
            if violations:
                yield _sse_event({
                    "type": "style_check",
                    "status": "running",
                    "message": f"发现 {len(violations)} 处禁用句式，正在自动修订",
                    "violations": violations[:8],
                })
                try:
                    repaired, before, remaining = await _repair_forbidden_sentence_text(
                        full_text,
                        project,
                        model,
                        max_tokens,
                    )
                    full_text = repaired
                    yield _sse_event({
                        "type": "style_repaired",
                        "status": "ok" if not remaining else "warning",
                        "message": "禁用句式已自动修订" if not remaining else f"仍有 {len(remaining)} 处需要人工确认",
                        "full_text": full_text,
                        "violations": before[:8],
                        "remaining": remaining[:8],
                    })
                except Exception as exc:
                    yield _sse_event({
                        "type": "style_repaired",
                        "status": "error",
                        "message": f"禁用句式自动修订失败：{exc}",
                        "full_text": full_text,
                        "violations": violations[:8],
                    })
        done_data = json.dumps(
            {"type": "done", "full_text": full_text},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        yield f"data: {done_data}\n\n"
        yield "data: [DONE]\n\n"
    except LLMError as e:
        error_data = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False, separators=(",", ":"))
        yield f"data: {error_data}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        error_data = json.dumps(
            {"type": "error", "message": f"服务器错误: {e}"},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        yield f"data: {error_data}\n\n"
        yield "data: [DONE]\n\n"


def _sse_event(payload) -> str:
    if payload == "[DONE]":
        return "data: [DONE]\n\n"
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"data: {data}\n\n"


# ---------------------------------------------------------------------------
# Narrator generation (SSE)
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/ai/generate/narrator")
async def generate_narrator(project_id: str, payload: NarratorGenerateRequest, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    _get_outline_node_or_404(db, project_id, payload.outline_node_id)

    async def event_generator():
        world_ctx = _build_world_context(db, project_id, payload.outline_node_id)
        summaries = _build_recent_summaries(db, project_id, payload.context_chapters)
        outline_ctx = _build_outline_context(db, project_id, payload.outline_node_id)
        scene_chars = _build_scene_characters_context(db, project_id, payload.outline_node_id)
        style_ctx = _build_style_context(project)

        system_prompt = (
            "你是一位资深小说叙述者，专精于场景描写、气氛渲染、动作刻画与剧情推进。\n"
            "你的文字追求：画面感（调动读者五感，让场景可见可闻可触）、节奏感（按剧情张力调整句段长短，紧张时短促，从容时舒展）、\n"
            "一致性（严格遵守世界观规则和角色设定，不做越界发挥）。\n\n"
            "【必须遵守】\n"
            "1. 只输出叙述文本——包括场景描写、动作刻画、心理活动（限第三人称叙述者视角）、环境渲染。严禁输出角色对话。\n"
            "2. 严格遵循【世界观设定】中的规则体系，不得自行发明或篡改任何设定。\n"
            "3. 与【风格设定】保持一致的叙事视角和文风，不得在人称之间跳转。\n"
            "4. 若【当前大纲】提供了具体场景指示，必须覆盖大纲中标注的核心事件和冲突点，不得偏离主线。\n"
            "5. 若【前文摘要】提供了近期情节，必须保持时间线和因果链连贯，不得与前文矛盾。\n\n"
            "【禁止事项】\n"
            "- 禁止输出元评论（如“好的，我来写...”、“以下是场景描写...”）。直接进入正文。\n"
            "- 禁止以「本章概要」、「内容提要」等摘要形式输出。必须写出完整场景叙事，而非概括性描述。\n"
            "- 禁止将角色对话写入叙述段落。角色间的言语交流只能通过间接引语或叙述性概括体现。\n"
            "- 禁止使用空泛形容词堆砌（如「非常强大」、「极其神秘」）。每个描述必须有具体可感的细节支撑。\n"
            "- 禁止在缺乏上下文时突然引入新角色、新地点或新设定。\n\n"
            "【质量标准】\n"
            "- 好的叙述：包含具体感官细节（视觉/听觉/触觉/嗅觉/味觉），读者能「看到」场景。\n"
            "- 好的动作：每个动作有因果链——谁做了什么、为什么做、产生了什么后果。\n"
            "- 好的渲染：环境描写服务于情绪和主题，而非单纯的风景描述。\n"
            "- 避免：大段内心独白（留给角色AI）、信息倾销式背景介绍（融入剧情逐步揭示）。\n\n"
            "【边界情况】\n"
            "- 若【当前大纲】信息不足：基于已有角色和世界观合理推进情节，但不引入大纲未授权的新冲突线。\n"
            "- 若【场景角色】列出了角色但未指定行为：根据角色性格和当前场景，为其分配合乎人设的自然行为。\n"
            "- 若【前文摘要】为空：说明这是开篇场景，从零开始建立场景感和角色形象。\n\n"
            f"【世界观设定】\n{world_ctx}\n\n"
            f"【风格设定】\n{style_ctx}\n\n"
            f"【当前大纲】\n{outline_ctx}\n\n"
            f"【场景角色】\n{scene_chars}\n\n"
            f"【前文摘要】\n{summaries}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload.prompt},
        ]
        gen = LLMGateway.stream_chat_completion(
            messages=messages,
            model=payload.model,
            temperature=payload.temperature or 0.7,
            max_tokens=payload.max_tokens,
        )
        async for event in _sse_writer_stream(gen, project=project, model=payload.model, max_tokens=payload.max_tokens):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Character dialogue generation (SSE)
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/ai/generate/character/{character_id}")
async def generate_character_dialogue(
    project_id: str,
    character_id: str,
    payload: CharacterDialogueRequest,
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(db, project_id)
    character = _get_character_or_404(db, project_id, character_id)
    _get_outline_node_or_404(db, project_id, payload.outline_node_id)

    async def event_generator():
        char_ctx = _build_character_context(character)
        ai_ctx = _build_character_ai_context(character)
        timeline = _build_character_timeline(db, character_id)
        relationships = _build_character_relationships(db, project_id, character_id)
        summaries = _build_recent_summaries(db, project_id, payload.context_chapters)
        outline_ctx = _build_outline_context(db, project_id, payload.outline_node_id)
        scene_chars = _build_scene_characters_context(db, project_id, payload.outline_node_id)
        style_ctx = _build_style_context(project)

        config = character.ai_config
        model_override = payload.model or (config.model_override if config else None)

        system_prompt = (
            f"你是小说《{project.title}》中的角色「{character.name}」。\n"
            "你必须完全沉浸在这个角色的身份中，以该角色的视角、知识范围、价值观和情感状态来感知和回应世界。\n\n"
            "【角色扮演原则】\n"
            "1. 你只知道自己角色所知的事情——你没有上帝视角，不知道其他角色的内心想法，不知道未发生在你面前的事件。\n"
            "2. 你的言语和行动必须符合你的性格描述、背景经历和能力范围。一个怯懦的角色不会突然变得勇敢，除非【近期经历】中有合理促发事件。\n"
            "3. 你的情感反应应符合当前场景的语境和情感倾向设定，不应无故剧烈震荡。\n"
            "4. 你对他人的态度应反映【角色关系】中的亲疏远近和过往历史，不应毫无来由地信任或敌视。\n\n"
            "【输出格式】\n"
            "- 输出该角色的对话、行为描写或内心独白。可混合使用：直接引语（「……」）、动作叙述、心理活动。\n"
            "- 对话应具有潜台词层次——表面意思与实际意图可以存在差距，让读者能「听出」未说出口的东西。\n"
            "- 内心独白应体现角色真实的困惑、欲望或矛盾，而非简单复述当前发生的事。\n"
            "- 行为描写应具有目的性——每个动作服务于情感表达或剧情推进，而非无意义的肢体动作。\n\n"
            "【禁止事项】\n"
            "- 禁止输出元评论（如「作为XXX，我会说...」、「好的，我来以这个角色的身份发言...」）。直接输出角色内容。\n"
            "- 禁止跳出角色视角——不描述其他角色的内心活动，不对剧情走向做客观评述。\n"
            "- 禁止代替其他角色发言或预设他们的反应。你的输出仅限于你自己角色的言行。\n"
            "- 禁止说出与自己性格、背景或能力矛盾的话。\n"
            "- 禁止使用不符合角色世界观的现代网络用语、英语夹杂或跨世界观词汇，除非角色背景明确支持。\n\n"
            "【对话质量指南】\n"
            "- 好的对白：通过说话方式本身展示性格——用词习惯、句式长短、礼貌程度、口头禅的自然运用。\n"
            "- 好的独白：揭示角色不知道该如何向他人表达的东西，而非复述读者已知的事实。\n"
            "- 好的行为：动作有明确动机和后果，不是单纯的身体移动。\n"
            "- 避免：台词空洞无信息量（连续出现「嗯」、「好的」、「知道了」）、过度解释情感而非展示、平铺直叙角色动机。\n\n"
            f"【角色档案】\n{char_ctx}\n\n"
            f"【AI对话参数】\n{ai_ctx}\n\n"
            f"【角色关系】\n{relationships}\n\n"
            f"【近期经历】\n{timeline}\n\n"
            f"【作品文风约束】\n{style_ctx}\n\n"
            f"【场景上下文】\n{scene_chars}\n\n"
            f"【当前大纲】\n{outline_ctx}\n\n"
            f"【前文摘要】\n{summaries}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload.prompt},
        ]
        gen = LLMGateway.stream_chat_completion(
            messages=messages,
            model=model_override,
            temperature=payload.temperature or 0.8,
            max_tokens=payload.max_tokens,
        )
        async for event in _sse_writer_stream(gen, project=project, model=model_override, max_tokens=payload.max_tokens):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Dialogue battle mode (SSE)
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/ai/generate/dialogue-battle")
async def generate_dialogue_battle(
    project_id: str,
    payload: DialogueBattleRequest,
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(db, project_id)
    _get_outline_node_or_404(db, project_id, payload.outline_node_id)

    characters = []
    for cid in payload.character_ids:
        characters.append(_get_character_or_404(db, project_id, cid))

    async def event_generator():
        world_ctx = _build_world_context(db, project_id, payload.outline_node_id)
        summaries = _build_recent_summaries(db, project_id, payload.context_chapters)
        outline_ctx = _build_outline_context(db, project_id, payload.outline_node_id)
        scene_chars = _build_scene_characters_context(db, project_id, payload.outline_node_id)
        style_ctx = _build_style_context(project)

        dialogue_history: list[dict] = []
        yield f"data: {json.dumps({'type': 'battle_start', 'character_ids': payload.character_ids, 'turns': payload.turns}, ensure_ascii=False, separators=(',', ':'))}\n\n"

        for turn in range(payload.turns):
            for char in characters:
                char_ctx = _build_character_context(char)
                ai_ctx = _build_character_ai_context(char)
                timeline = _build_character_timeline(db, char.id)
                relationships = _build_character_relationships(db, project_id, char.id)
                config = char.ai_config
                model_override = payload.model or (config.model_override if config else None)

                history_text = "\n".join(
                    f"{h['character_name']}: {h['content']}" for h in dialogue_history[-6:]
                ) if dialogue_history else "（对话刚开始）"

                system_prompt = (
                    f"你是小说《{project.title}》中的角色「{char.name}」。\n"
                    "你必须完全沉浸在这个角色的身份中，以该角色的视角、知识范围和情感状态来感知和回应世界。\n\n"
                    "【角色扮演原则】\n"
                    "1. 你只知道自己角色所知的事情——没有上帝视角，不知道其他角色的内心想法。\n"
                    "2. 你的言语和行动必须符合你的性格描述、背景经历和能力范围。\n"
                    "3. 你的情感反应应符合当前场景语境和情感倾向设定。\n"
                    "4. 你对他人的态度应反映【角色关系】中的亲疏远近和历史。\n\n"
                    "【回合制对话规则】\n"
                    "1. 仔细阅读【对话历史】中其他角色说过的话，你的回应必须承接上文，不能无视他人发言自言自语。\n"
                    "2. 回应应推动对话向前——提出新信息、表达态度、做出选择或反问，而非简单附和或重复。\n"
                    "3. 对话节奏应有变化：需要时可以沉默或简短回应，冲突时可以激烈或长篇表达，日常场景可以轻松自然。\n"
                    "4. 如果上一轮有人向你提出了问题或挑战，你必须做出回应，不能无故回避（除非回避本身就是角色性格的体现，此时用行为描写表明你在回避）。\n\n"
                    "【输出格式】\n"
                    "- 输出该角色的对话、行为描写或内心独白。\n"
                    "- 对话应具有潜台词层次——表面意思与实际意图可以存在差距。\n"
                    "- 行为描写应服务于情感表达或剧情推进。\n\n"
                    "【禁止事项】\n"
                    "- 禁止输出元评论。直接输出角色内容。\n"
                    "- 禁止跳出角色视角或做客观评述。\n"
                    "- 禁止代替其他角色发言或预设他们的反应。\n"
                    "- 禁止说出与角色设定矛盾的话。\n"
                    "- 禁止无视【对话历史】自说自话。\n\n"
                    f"【角色档案】\n{char_ctx}\n\n"
                    f"【AI对话参数】\n{ai_ctx}\n\n"
                    f"【角色关系】\n{relationships}\n\n"
                    f"【近期经历】\n{timeline}\n\n"
                    f"【作品文风约束】\n{style_ctx}\n\n"
                    f"【世界观】\n{world_ctx}\n\n"
                    f"【当前大纲】\n{outline_ctx}\n\n"
                    f"【场景角色】\n{scene_chars}\n\n"
                    f"【前文摘要】\n{summaries}\n\n"
                    f"【对话历史】\n{history_text}"
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"场景：{payload.prompt}\n请以{char.name}的身份发言。"},
                ]

                yield f"data: {json.dumps({'type': 'turn_start', 'character_id': char.id, 'character_name': char.name, 'turn': turn + 1}, ensure_ascii=False, separators=(',', ':'))}\n\n"

                full_text = ""
                try:
                    gen = LLMGateway.stream_chat_completion(
                        messages=messages,
                        model=model_override,
                        temperature=payload.temperature or 0.8,
                        max_tokens=payload.max_tokens,
                    )
                    async for chunk in gen:
                        full_text += chunk
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False, separators=(',', ':'))}\n\n"

                    violations = _detect_forbidden_sentence_violations(full_text, project)
                    if violations:
                        yield _sse_event({
                            "type": "style_check",
                            "status": "running",
                            "message": f"{char.name} 的输出命中禁用句式，正在自动修订",
                            "violations": violations[:8],
                        })
                        try:
                            repaired, before, remaining = await _repair_forbidden_sentence_text(
                                full_text,
                                project,
                                model_override,
                                payload.max_tokens,
                            )
                            full_text = repaired
                            yield _sse_event({
                                "type": "style_repaired",
                                "status": "ok" if not remaining else "warning",
                                "message": "禁用句式已自动修订" if not remaining else f"仍有 {len(remaining)} 处需要人工确认",
                                "full_text": full_text,
                                "violations": before[:8],
                                "remaining": remaining[:8],
                            })
                        except Exception as repair_exc:
                            yield _sse_event({
                                "type": "style_repaired",
                                "status": "error",
                                "message": f"禁用句式自动修订失败：{repair_exc}",
                                "full_text": full_text,
                                "violations": violations[:8],
                            })

                    dialogue_history.append({"character_id": char.id, "character_name": char.name, "content": full_text})
                    yield f"data: {json.dumps({'type': 'turn_end', 'character_id': char.id, 'character_name': char.name, 'full_text': full_text}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False, separators=(',', ':'))}\n\n"

        yield f"data: {json.dumps({'type': 'battle_complete', 'dialogue': dialogue_history}, ensure_ascii=False, separators=(',', ':'))}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Rewrite
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/ai/rewrite")
async def rewrite_text(project_id: str, payload: RewriteRequest, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    style_ctx = _build_style_context(project)
    style_instruction = STYLE_PROMPTS.get(payload.style, "") if payload.style else ""

    system_prompt = (
        "你是一位资深小说文字编辑，专精于文本改写——在不改变核心意思的前提下，重新组织语言、调整表达方式、提升文字质感。\n\n"
        "【改写原则】\n"
        "1. 核心意思必须完整保留：事件、情感走向、角色言行的事实层面不得改变。\n"
        "2. 改变的是表达方式：句式结构、词汇选择、描写角度、详略比例。\n"
        "3. 如果用户指定了风格倾向，严格按对应风格执行。\n"
        "4. 改写后的文本应与【风格设定】中作品的叙事视角和文风偏好保持一致。\n\n"
        "【禁止事项】\n"
        "- 禁止新增原文没有的剧情事件、角色行动或对话内容。\n"
        "- 禁止删除原文中的关键信息或情节节点。\n"
        "- 禁止改变叙事视角（如将第一人称改为第三人称）或时态。\n"
        "- 禁止输出任何解释、点评或元评论。只输出改写后的文本。\n"
        "- 禁止以「改写如下」、「修改后的文本：」等引导语开头。\n\n"
        "【质量判断】\n"
        "- 好的改写：读起来像原文的「更好版本」——更流畅、更有力、更有风格，但信息不变。\n"
        "- 失败的改写：改变了原意、丢失了信息、或只是替换了几个近义词。\n\n"
        f"【风格设定】\n{style_ctx}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{style_instruction}\n{payload.prompt or '请改写以下文本：'}\n\n原文：\n{payload.text}"},
    ]
    result = await LLMGateway.chat_completion(
        messages=messages,
        model=payload.model,
        temperature=payload.temperature or 0.7,
        max_tokens=payload.max_tokens,
    )
    rewritten, violations, remaining = await _repair_forbidden_sentence_text(
        result.get("content", ""),
        project,
        payload.model,
        payload.max_tokens,
    )
    return ApiResponse.success(data={
        "original": payload.text,
        "rewritten": rewritten,
        "style": payload.style,
        "model": result.get("model"),
        "usage": result.get("usage"),
        "style_violations": violations,
        "style_remaining_violations": remaining,
    })


# ---------------------------------------------------------------------------
# Expand
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/ai/expand")
async def expand_text(project_id: str, payload: ExpandRequest, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    style_ctx = _build_style_context(project)

    system_prompt = (
        "你是一位资深小说扩写编辑，专精于在不改变原文骨架的前提下增加血肉——让场景更丰满、角色更立体、情感更深刻。\n\n"
        "【扩写原则】\n"
        "1. 原文中的每一句话、每一个事件、每一处描写必须全部保留。扩写是「加法」不是「替换」。\n"
        "2. 新增内容应自然地融入原文结构，而非集中堆砌在某一段落末尾。\n"
        "3. 可扩展的维度：环境氛围（感官细节）、动作过程（分解步骤）、心理活动（情感层次）、对话（潜台词与回应）、背景插叙（适时回忆或交代）。\n"
        "4. 扩展比例应均匀——不要将某一句放大十倍而其他部分原封不动。\n"
        "5. 新增内容必须与【风格设定】中作品的叙事视角和文风保持一致。\n\n"
        "【禁止事项】\n"
        "- 禁止删减、改写或移动原文中的任何已有内容。\n"
        "- 禁止添加原文未提及的新角色、新事件或新设定。\n"
        "- 禁止改变原文的叙事人称、时态或视角。\n"
        "- 禁止输出解释或元评论。只输出完整的扩写后文本。\n"
        "- 禁止以「扩写如下」、「以下是扩写后的文本」等引导语开头。\n\n"
        "【质量判断】\n"
        "- 好的扩写：读起来原文像是一个「大纲」，扩写后才是「成稿」——细节充沛但结构不变。\n"
        "- 失败的扩写：读起来像原文被拉长了——增加了字数但没有增加信息量或感染力。\n\n"
        f"【风格设定】\n{style_ctx}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{payload.prompt or '请扩写以下文本，增加更多细节：'}\n\n原文：\n{payload.text}"},
    ]
    result = await LLMGateway.chat_completion(
        messages=messages,
        model=payload.model,
        temperature=payload.temperature or 0.7,
        max_tokens=payload.max_tokens,
    )
    expanded, violations, remaining = await _repair_forbidden_sentence_text(
        result.get("content", ""),
        project,
        payload.model,
        payload.max_tokens,
    )
    return ApiResponse.success(data={
        "original": payload.text,
        "expanded": expanded,
        "model": result.get("model"),
        "usage": result.get("usage"),
        "style_violations": violations,
        "style_remaining_violations": remaining,
    })


# ---------------------------------------------------------------------------
# Continue
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/ai/continue")
async def continue_text(project_id: str, payload: ContinueRequest, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    _get_outline_node_or_404(db, project_id, payload.outline_node_id)
    style_ctx = _build_style_context(project)
    summaries = _build_recent_summaries(db, project_id, payload.context_chapters)
    outline_ctx = _build_outline_context(db, project_id, payload.outline_node_id)

    system_prompt = (
        "你是一位资深小说续写师，专精于从给定文本的结尾处无缝衔接，让读者察觉不到作者切换的痕迹。\n\n"
        "【续写原则】\n"
        "1. 从原文结尾处最后一个场景、最后一句对话、最后一个动作的自然延伸处开始写，不跳时间、不切场景（除非原文结尾本身就是场景结束的节点）。\n"
        "2. 严格承接上文：已出场角色的行为逻辑、情感状态、当前位置必须一致。已发生的剧情事实不可篡改或忽略。\n"
        "3. 若【当前大纲】指定了本段落的剧情方向，续写应朝该方向推进，但不跳过必要的过渡。\n"
        "4. 若【前文摘要】提供了更早的情节背景，确保因果链连贯——前面的伏笔可以在续写中发展，但不应立即全部收束。\n"
        "5. 文风、叙事视角、语气应与【风格设定】保持一致，且与上文无缝衔接。\n\n"
        "【禁止事项】\n"
        "- 禁止重复原文中已经写过的内容。续写是「接着写」不是「改写」或「重述」。\n"
        "- 禁止凭空引入上文和新【当前大纲】中均未提及的新角色、新设定或新冲突线。\n"
        "- 禁止在开头使用「在上一段中」、「此前」、「回顾上文」等回顾性表述。直接进入新内容。\n"
        "- 禁止改变叙事人称、时态或视角。\n"
        "- 禁止输出解释或元评论。\n\n"
        "【质量判断】\n"
        "- 好的续写：读起来就像同一个作者接着写下去——情节推进合理、角色行为一致、文风统一。\n"
        "- 失败的续写：读起来像另一个人写的同人——角色OOC、节奏突变、或引入不协调的新元素。\n\n"
        f"【风格设定】\n{style_ctx}\n\n"
        f"【当前大纲】\n{outline_ctx}\n\n"
        f"【前文摘要】\n{summaries}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{payload.prompt or '请从以下文本结尾处继续写：'}\n\n上文：\n{payload.text}\n\n请接着写下去："},
    ]
    result = await LLMGateway.chat_completion(
        messages=messages,
        model=payload.model,
        temperature=payload.temperature or 0.7,
        max_tokens=payload.max_tokens,
    )
    continuation, violations, remaining = await _repair_forbidden_sentence_text(
        result.get("content", ""),
        project,
        payload.model,
        payload.max_tokens,
    )
    return ApiResponse.success(data={
        "previous": payload.text[-200:] if len(payload.text) > 200 else payload.text,
        "continuation": continuation,
        "model": result.get("model"),
        "usage": result.get("usage"),
        "style_violations": violations,
        "style_remaining_violations": remaining,
    })


# ---------------------------------------------------------------------------
# Conflict suggestions
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/ai/conflict-suggest")
async def conflict_suggest(project_id: str, payload: ConflictSuggestRequest, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    _get_outline_node_or_404(db, project_id, payload.outline_node_id)
    outline_ctx = _build_outline_context(db, project_id, payload.outline_node_id)
    summaries = _build_recent_summaries(db, project_id, 5)

    characters = (
        db.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.updated_at.desc())
        .limit(10)
        .all()
    )
    char_context = "\n".join(
        f"- {c.name}（{c.role_type or '未分类'}）: {(c.personality or '')[:200]}"
        for c in characters
    ) or "暂无角色。"

    relationships = (
        db.query(CharacterRelationship)
        .filter(CharacterRelationship.project_id == project_id)
        .limit(20)
        .all()
    )
    rel_context = "\n".join(
        f"- {r.character_a_id[:8]} ↔ {r.character_b_id[:8]}: {r.relationship_type}"
        for r in relationships
    ) or "暂无已知关系。"

    messages = [
        {
            "role": "system",
            "content": (
                "你是一位资深小说情节编辑，专精于戏剧冲突设计。你深谙「没有冲突就没有故事」的原则，能为任何剧情阶段注入恰到好处的张力。\n\n"
                "【任务】\n"
                "根据当前剧情状态，分析并设计3种不同类型的冲突方案，每种类型提供一个具体建议。\n\n"
                "【冲突类型定义】\n"
                "- personality（人物冲突）：角色之间的矛盾——目标对立、价值观碰撞、误解、背叛、竞争。此类型必须指定两个以上具体角色名。\n"
                "- faction（势力冲突）：组织或阵营之间的对抗——门派争斗、国家战争、阶级对立、资源争夺。此类型必须明确对立的双方。\n"
                "- inner（内心冲突）：角色内在的挣扎——道德困境、欲望与责任的拉扯、自我认同的危机、创伤后应激。此类型聚焦单一角色的心理层面。\n\n"
                "【设计原则】\n"
                "1. 每个冲突必须基于已有的角色、关系和世界观设定——不能凭空创造不存在的新势力或新人物。\n"
                "2. 每个冲突必须有清晰的起因（为什么现在爆发）、过程（冲突如何升级）和可行方向（如何解决或恶化）。\n"
                "3. tension_level（张力等级）的判断标准：low=可缓和的分歧、medium=需要做出选择的矛盾、high=不可调和的对抗。\n"
                "4. 冲突建议应具体可落地——详细描述冲突场景而非抽象概念。\n\n"
                "【禁止事项】\n"
                "- 禁止建议与已有剧情和角色设定矛盾或重复的冲突。\n"
                "- 禁止引入【角色列表】中不存在的角色。\n"
                "- 禁止输出JSON以外的任何内容。\n\n"
                "【输出格式】\n"
                "只输出JSON对象，格式：\n"
                "{\"conflicts\":[{\"type\":\"personality|faction|inner\",\"title\":\"\",\"description\":\"\",\"involved_characters\":[\"\"],\"tension_level\":\"low|medium|high\",\"suggested_outcome\":\"\"}]}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"作品：{project.title}\n"
                f"简介：{project.description or '暂无'}\n\n"
                f"【当前大纲】\n{outline_ctx}\n\n"
                f"【前文摘要】\n{summaries}\n\n"
                f"【角色列表】\n{char_context}\n\n"
                f"【已知关系】\n{rel_context}\n\n"
                f"{'用户倾向: ' + payload.prompt if payload.prompt else ''}\n\n"
                "请分析并提供3种情节冲突建议。"
            ),
        },
    ]
    result = await LLMGateway.chat_completion(
        messages=messages,
        model=payload.model,
        temperature=payload.temperature or 0.8,
    )

    suggestion_text = result.get("content", "")
    parsed = None
    try:
        parsed = json.loads(suggestion_text.strip().removeprefix("```json").removesuffix("```").strip())
    except json.JSONDecodeError:
        parsed = None

    return ApiResponse.success(data={
        "conflicts": parsed.get("conflicts", []) if parsed else [],
        "raw_text": suggestion_text,
        "model": result.get("model"),
        "usage": result.get("usage"),
    })


def _conflict_child_type(parent: OutlineNode) -> str:
    if parent.node_type == "volume":
        return "chapter"
    return "section"


def _next_child_sort_order(db: Session, project_id: str, parent_id: str) -> int:
    last_child = (
        db.query(OutlineNode)
        .filter(OutlineNode.project_id == project_id, OutlineNode.parent_id == parent_id)
        .order_by(OutlineNode.sort_order.desc(), OutlineNode.created_at.desc())
        .first()
    )
    return (last_child.sort_order + 1) if last_child else 0


def _resolve_conflict_character_ids(
    db: Session,
    project_id: str,
    names: list[str],
    character_ids: list[str],
) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for character_id in character_ids:
        character = (
            db.query(Character)
            .filter(Character.id == character_id, Character.project_id == project_id)
            .first()
        )
        if not character:
            raise ValidationError("采纳冲突建议时，关联角色必须属于当前作品")
        if character.id not in seen:
            resolved.append(character.id)
            seen.add(character.id)

    clean_names = {name.strip() for name in names if name and name.strip()}
    if clean_names:
        characters = (
            db.query(Character)
            .filter(Character.project_id == project_id, Character.name.in_(clean_names))
            .all()
        )
        for character in characters:
            if character.id not in seen:
                resolved.append(character.id)
                seen.add(character.id)
    return resolved


def _adopted_outline_node_payload(node: OutlineNode) -> dict:
    return {
        "id": node.id,
        "project_id": node.project_id,
        "parent_id": node.parent_id,
        "node_type": node.node_type,
        "title": node.title,
        "summary": node.summary,
        "status": node.status,
        "sort_order": node.sort_order,
        "linked_characters": [
            {
                "id": link.character.id,
                "name": link.character.name,
                "role_type": link.character.role_type,
                "role_in_scene": link.role_in_scene,
            }
            for link in node.linked_characters
            if link.character is not None
        ],
    }


@router.post("/projects/{project_id}/ai/conflict-adopt")
def adopt_conflict_suggestion(
    project_id: str,
    payload: ConflictAdoptRequest,
    db: Session = Depends(get_db),
):
    """Adopt a generated conflict suggestion as a child outline node."""
    _get_project_or_404(db, project_id)
    parent = _get_outline_node_or_404(db, project_id, payload.outline_node_id)
    if parent is None:
        raise ValidationError("采纳冲突建议时必须提供父级大纲节点")

    summary_parts = [payload.description.strip()]
    if payload.suggested_outcome and payload.suggested_outcome.strip():
        summary_parts.append(f"建议走向：{payload.suggested_outcome.strip()}")
    if payload.type and payload.type.strip():
        summary_parts.append(f"冲突类型：{payload.type.strip()}")

    node = OutlineNode(
        project_id=project_id,
        parent_id=parent.id,
        node_type=_conflict_child_type(parent),
        title=payload.title.strip(),
        summary="\n".join(summary_parts),
        status="pending",
        sort_order=_next_child_sort_order(db, project_id, parent.id),
    )
    db.add(node)
    db.flush()

    for character_id in _resolve_conflict_character_ids(
        db,
        project_id,
        payload.involved_characters,
        payload.involved_character_ids,
    ):
        node.linked_characters.append(
            OutlineNodeCharacter(character_id=character_id, role_in_scene="conflict")
        )

    db.commit()
    db.refresh(node)
    return ApiResponse.success(
        data={"outline_node": _adopted_outline_node_payload(node)},
        message="冲突建议已采纳为大纲节点",
    )


# ---------------------------------------------------------------------------
# Autonomous story assistant
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/ai/assistant/conversations")
async def list_assistant_conversations(project_id: str, scope: str = "writer", db: Session = Depends(get_db)):
    """List persisted assistant conversations for a project."""
    _get_project_or_404(db, project_id)
    conversations = (
        db.query(AssistantConversation)
        .filter(AssistantConversation.project_id == project_id, AssistantConversation.scope == scope)
        .order_by(AssistantConversation.updated_at.desc(), AssistantConversation.created_at.desc())
        .all()
    )
    items = []
    for conversation in conversations:
        message_count = (
            db.query(AssistantMessage)
            .filter(AssistantMessage.conversation_id == conversation.id)
            .count()
        )
        items.append(_assistant_conversation_to_dict(conversation, message_count))
    return ApiResponse.success(data={"items": items, "total": len(items)})


@router.post("/projects/{project_id}/ai/assistant/conversations")
async def create_assistant_conversation(
    project_id: str,
    payload: AssistantConversationCreate,
    db: Session = Depends(get_db),
):
    """Create a new assistant conversation."""
    _get_project_or_404(db, project_id)
    _get_outline_node_or_404(db, project_id, payload.outline_node_id)
    conversation = AssistantConversation(
        project_id=project_id,
        title=(payload.title or "新对话").strip()[:200] or "新对话",
        current_chapter_id=payload.chapter_id,
        current_outline_node_id=payload.outline_node_id,
        model=payload.model,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ApiResponse.success(data=_assistant_conversation_to_dict(conversation, 0), message="助手对话已创建")


@router.get("/projects/{project_id}/ai/assistant/conversations/{conversation_id}")
async def get_assistant_conversation(
    project_id: str,
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Get one persisted assistant conversation and all messages."""
    conversation = _get_assistant_conversation_or_404(db, project_id, conversation_id)
    messages = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.conversation_id == conversation.id)
        .order_by(
            AssistantMessage.created_at.asc(),
            AssistantMessage.role.desc(),
            AssistantMessage.updated_at.asc(),
            AssistantMessage.id.asc(),
        )
        .all()
    )
    return ApiResponse.success(data={
        "conversation": _assistant_conversation_to_dict(conversation, len(messages)),
        "messages": [_assistant_message_to_dict(message) for message in messages],
    })


@router.put("/projects/{project_id}/ai/assistant/conversations/{conversation_id}")
async def update_assistant_conversation(
    project_id: str,
    conversation_id: str,
    payload: AssistantConversationUpdate,
    db: Session = Depends(get_db),
):
    """Update assistant conversation metadata."""
    conversation = _get_assistant_conversation_or_404(db, project_id, conversation_id)
    if payload.title is not None:
        conversation.title = payload.title.strip()[:200] or conversation.title
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conversation)
    return ApiResponse.success(data=_assistant_conversation_to_dict(conversation), message="助手对话已更新")


@router.delete("/projects/{project_id}/ai/assistant/conversations/{conversation_id}")
async def delete_assistant_conversation(
    project_id: str,
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Delete an assistant conversation."""
    conversation = _get_assistant_conversation_or_404(db, project_id, conversation_id)
    db.delete(conversation)
    db.commit()
    return ApiResponse.success(message="助手对话已删除")


@router.put("/projects/{project_id}/ai/assistant/messages/{message_id}")
async def update_assistant_message(
    project_id: str,
    message_id: str,
    payload: AssistantMessageUpdate,
    db: Session = Depends(get_db),
):
    """Edit a persisted user message without regenerating."""
    _get_project_or_404(db, project_id)
    message = (
        db.query(AssistantMessage)
        .join(AssistantConversation, AssistantConversation.id == AssistantMessage.conversation_id)
        .filter(
            AssistantConversation.project_id == project_id,
            AssistantMessage.id == message_id,
        )
        .first()
    )
    if not message:
        raise NotFoundError("助手消息不存在")
    if message.role != "user":
        raise ValidationError("只能修改用户发送的消息")
    message.content = payload.content.strip()
    message.updated_at = datetime.utcnow()
    message.conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(message)
    return ApiResponse.success(data=_assistant_message_to_dict(message), message="消息已更新")

@router.post("/projects/{project_id}/ai/assistant")
async def story_assistant(
    project_id: str,
    payload: StoryAssistantRequest,
    db: Session = Depends(get_db),
):
    """Conversational writing assistant that plans local tool use, reads project context, and can create chapters."""
    project = _get_project_or_404(db, project_id)
    selected_chapter = None
    if payload.chapter_id:
        selected_chapter = (
            db.query(Chapter)
            .filter(Chapter.project_id == project_id, Chapter.id == payload.chapter_id)
            .first()
        )
    outline_node_id = payload.outline_node_id or (selected_chapter.outline_node_id if selected_chapter else None)
    _get_outline_node_or_404(db, project_id, outline_node_id)
    history_text = _assistant_history_text(payload.history)

    planner_messages = [
        {
            "role": "system",
            "content": (
                "你是小说写作助手的工具调度器。你要根据用户消息判断接下来需要读取哪些项目资料，"
                "以及是否需要让角色AI参与扮演、是否可能创建新章节。只输出JSON对象。\n"
                "可用工具：read_recent_summaries, read_outline, read_worldbuilding, read_characters, "
                "read_relationships, read_chapter_detail, roleplay_characters。\n"
                "输出格式：{\"intent\":\"advise|check|write|create_chapter|worldbuilding\","
                "\"tools\":[\"read_recent_summaries\"],\"character_names\":[\"\"],"
                "\"needs_worldbuilding\":false,\"should_create_chapter\":false,"
                "\"chapter_title\":\"\",\"reason\":\"\"}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"作品：{project.title}\n"
                f"当前章节：{selected_chapter.title if selected_chapter else '未选择'}\n"
                f"对话历史：\n{history_text}\n\n"
                f"用户需求：{payload.message}"
            ),
        },
    ]
    planner_error = None
    try:
        planner_result = await LLMGateway.chat_completion(
            messages=planner_messages,
            model=payload.model,
            temperature=0.2,
            max_tokens=1000,
            retry=1,
        )
        plan = _normalize_assistant_plan(_parse_json_object(planner_result.get("content", "")), payload.message)
    except LLMError as exc:
        planner_error = str(exc)
        plan = _normalize_assistant_plan(None, payload.message)

    tool_logs = []
    context_sections: list[str] = []

    summaries = _build_recent_summaries(db, project_id, payload.context_chapters)
    outline_ctx = _build_outline_context(db, project_id, outline_node_id)

    if planner_error:
        tool_logs.append({"tool": "plan_tools", "status": "fallback", "detail": planner_error})
    else:
        tool_logs.append({"tool": "plan_tools", "status": "ok", "detail": plan.get("reason")})

    if "read_recent_summaries" in plan["tools"]:
        context_sections.append(f"【前文摘要】\n{summaries}")
        tool_logs.append({"tool": "read_recent_summaries", "status": "ok", "detail": f"最近 {payload.context_chapters} 章"})

    if "read_outline" in plan["tools"]:
        outline_overview = _build_outline_overview(db, project_id)
        context_sections.append(f"【当前大纲节点】\n{outline_ctx}\n\n【全局大纲概览】\n{outline_overview}")
        tool_logs.append({"tool": "read_outline", "status": "ok", "detail": "已读取当前节点和大纲概览"})

    if "read_worldbuilding" in plan["tools"]:
        context_sections.append(f"【世界观设定】\n{_build_world_context(db, project_id, outline_node_id)}")
        tool_logs.append({"tool": "read_worldbuilding", "status": "ok", "detail": "已读取世界观条目"})

    if "read_characters" in plan["tools"]:
        context_sections.append(f"【角色档案】\n{_build_character_catalog(db, project_id)}")
        tool_logs.append({"tool": "read_characters", "status": "ok", "detail": "已读取角色档案"})

    if "read_relationships" in plan["tools"]:
        context_sections.append(f"【角色关系】\n{_build_relationship_context(db, project_id)}")
        tool_logs.append({"tool": "read_relationships", "status": "ok", "detail": "已读取角色关系"})

    if "read_chapter_detail" in plan["tools"]:
        context_sections.append(
            f"【当前章节正文】\n{_build_chapter_detail_context(db, project_id, payload.chapter_id)}\n\n"
            f"【最近章节正文片段】\n{_build_recent_chapter_details(db, project_id)}"
        )
        tool_logs.append({"tool": "read_chapter_detail", "status": "ok", "detail": "已读取当前章节和最近章节正文片段"})

    if history_text != "暂无对话历史。":
        context_sections.append(f"【对话历史与上一轮草稿】\n{history_text}")

    roleplay_results = []
    if "roleplay_characters" in plan["tools"]:
        roleplay_characters = _resolve_assistant_characters(
            db,
            project_id,
            plan.get("character_names") or [],
            outline_node_id,
        )
        for character in roleplay_characters:
            try:
                roleplay_results.append(await _assistant_character_roleplay(
                    db,
                    project_id,
                    character,
                    payload.message,
                    outline_ctx,
                    summaries,
                    payload.model,
                ))
            except LLMError as exc:
                roleplay_results.append({
                    "character_id": character.id,
                    "character_name": character.name,
                    "should_act": False,
                    "action_type": "error",
                    "content": "",
                    "rationale": str(exc),
                })
        context_sections.append(f"【角色AI扮演判断】\n{json.dumps(roleplay_results, ensure_ascii=False)}")
        tool_logs.append({"tool": "roleplay_characters", "status": "ok", "detail": f"{len(roleplay_results)} 个角色"})

    final_messages = [
        {
            "role": "system",
            "content": (
                "你是一个会使用项目资料的小说写作总控AI。你已经拿到了后端工具读取出的资料和角色AI扮演结果。"
                "请完成用户需求：可以判断剧情是否合理、指出矛盾、建议补充世界观、预测后续发展，或生成可导入的新章节草稿。\n\n"
                "要求：\n"
                "1. 只基于给定资料推断，不要无依据改写既有设定。\n"
                "2. 如果发现用户想写的剧情会破坏角色动机、时间线或世界观规则，要明确指出并给出改法。\n"
                "3. 如果世界观缺口会影响剧情成立，在 worldbuilding_suggestions 中给出可直接导入的设定条目。\n"
                "4. 如果角色AI判断某角色应行动，把这些行动自然合并进建议或章节草稿。\n"
                "5. 如果用户要求创建/写新章节，chapter_draft.content 必须是完整正文草稿，不是大纲。\n"
                "6. outline_node_id 必须从给定资料中【当前大纲节点】或【全局大纲概览】里显示的 [ID: xxx] 复制。如果资料中没有显示任何节点ID，或你不确定对应哪个节点，将 outline_node_id 设为空字符串 \"\"。严禁自行编造或猜测ID。\n"
                "7. 只输出JSON对象。\n\n"
                "输出格式：{\"reply\":\"给用户看的回答\","
                "\"reasonableness\":\"reasonable|needs_revision|contradictory|unclear\","
                "\"issues\":[\"\"],\"suggestions\":[\"\"],"
                "\"worldbuilding_suggestions\":[{\"dimension\":\"geography|history|factions|power_system|races|culture\","
                "\"title\":\"\",\"content\":\"\",\"reason\":\"\"}],"
                "\"chapter_draft\":{\"should_create\":false,\"title\":\"\",\"content\":\"\",\"summary\":\"\","
                "\"involved_characters\":[\"\"],\"outline_node_id\":\"\"}}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"作品：{project.title}\n"
                f"简介：{project.description or '暂无'}\n"
                f"写作风格：\n{_build_style_context(project)}\n\n"
                f"工具计划：{json.dumps(plan, ensure_ascii=False)}\n\n"
                f"{chr(10).join(context_sections)}\n\n"
                f"用户需求：{payload.message}"
            ),
        },
    ]
    final_result = await LLMGateway.chat_completion(
        messages=final_messages,
        model=payload.model,
        temperature=payload.temperature or 0.5,
        max_tokens=payload.max_tokens,
    )
    parsed = _parse_json_object(final_result.get("content", ""))
    if not parsed:
        parsed = {
            "reply": final_result.get("content", ""),
            "reasonableness": "unclear",
            "issues": [],
            "suggestions": [],
            "worldbuilding_suggestions": [],
            "chapter_draft": {"should_create": False, "title": "", "content": "", "summary": "", "involved_characters": []},
        }

    style_reports = await _repair_assistant_parsed_style(parsed, project, payload.model, payload.max_tokens)
    if style_reports:
        fixed_count = sum(1 for item in style_reports if item.get("fixed"))
        tool_logs.append({
            "tool": "style_guard",
            "status": "ok" if fixed_count == len(style_reports) else "warning",
            "detail": f"已检查禁用句式，修订 {fixed_count}/{len(style_reports)} 个字段",
        })

    draft = parsed.get("chapter_draft") if isinstance(parsed.get("chapter_draft"), dict) else {}
    created_chapter = None
    should_create = payload.auto_create_chapter and (
        bool(draft.get("should_create")) or bool(plan.get("should_create_chapter"))
    )
    if should_create:
        created = _create_assistant_chapter(
            db,
            project_id,
            str(draft.get("title") or plan.get("chapter_title") or "AI生成章节"),
            str(draft.get("content") or ""),
            str(draft.get("outline_node_id") or outline_node_id or "") or None,
            str(draft.get("summary") or parsed.get("reply") or ""),
            [str(name) for name in (draft.get("involved_characters") or []) if name],
            payload.model,
        )
        if created:
            db.commit()
            db.refresh(created)
            created_chapter = {
                "id": created.id,
                "title": created.title,
                "outline_node_id": created.outline_node_id,
                "word_count": created.word_count or 0,
            }
            tool_logs.append({"tool": "create_chapter", "status": "ok", "detail": created.title})
        else:
            tool_logs.append({"tool": "create_chapter", "status": "skipped", "detail": "草稿标题或正文为空"})

    return ApiResponse.success(data={
        "reply": str(parsed.get("reply") or ""),
        "reasonableness": parsed.get("reasonableness") or "unclear",
        "issues": parsed.get("issues") if isinstance(parsed.get("issues"), list) else [],
        "suggestions": parsed.get("suggestions") if isinstance(parsed.get("suggestions"), list) else [],
        "worldbuilding_suggestions": (
            parsed.get("worldbuilding_suggestions")
            if isinstance(parsed.get("worldbuilding_suggestions"), list)
            else []
        ),
        "chapter_draft": draft,
        "created_chapter": created_chapter,
        "plan": plan,
        "tool_logs": tool_logs,
        "roleplay_results": roleplay_results,
        "style_reports": style_reports,
        "model": final_result.get("model"),
        "usage": final_result.get("usage"),
    })


@router.post("/projects/{project_id}/ai/assistant/stream")
async def story_assistant_stream(
    project_id: str,
    payload: StoryAssistantRequest,
    db: Session = Depends(get_db),
):
    """SSE version of the autonomous writing assistant with live tool progress."""
    project = _get_project_or_404(db, project_id)
    selected_chapter = None
    if payload.chapter_id:
        selected_chapter = (
            db.query(Chapter)
            .filter(Chapter.project_id == project_id, Chapter.id == payload.chapter_id)
            .first()
        )
    outline_node_id = payload.outline_node_id or (selected_chapter.outline_node_id if selected_chapter else None)
    _get_outline_node_or_404(db, project_id, outline_node_id)

    async def event_generator():
        tool_logs = []
        context_sections: list[str] = []
        roleplay_results = []
        style_reports = []
        plan = None
        conversation = None
        user_message = None
        assistant_message = None
        draft_chapter: Optional[Chapter] = None
        draft_chapter_finalized = False

        try:
            if payload.edit_message_id:
                user_message = (
                    db.query(AssistantMessage)
                    .join(AssistantConversation, AssistantConversation.id == AssistantMessage.conversation_id)
                    .filter(
                        AssistantConversation.project_id == project_id,
                        AssistantMessage.id == payload.edit_message_id,
                    )
                    .first()
                )
                if not user_message:
                    raise NotFoundError("要修改的助手消息不存在")
                if user_message.role != "user":
                    raise ValidationError("只能修改用户发送的消息")
                conversation = user_message.conversation
                ordered_messages = (
                    db.query(AssistantMessage)
                    .filter(AssistantMessage.conversation_id == conversation.id)
                    .order_by(AssistantMessage.created_at.asc(), AssistantMessage.id.asc())
                    .all()
                )
                should_delete = False
                for stored_message in ordered_messages:
                    if should_delete:
                        db.delete(stored_message)
                    if stored_message.id == user_message.id:
                        should_delete = True
                user_message.content = payload.message
                user_message.status = "completed"
                user_message.updated_at = datetime.utcnow()
            else:
                if payload.conversation_id:
                    conversation = _get_assistant_conversation_or_404(db, project_id, payload.conversation_id)
                else:
                    conversation = AssistantConversation(
                        project_id=project_id,
                        title=_assistant_title_from_message(payload.message),
                    )
                    db.add(conversation)
                    db.flush()
                user_message = AssistantMessage(
                    conversation_id=conversation.id,
                    role="user",
                    content=payload.message,
                    status="completed",
                )
                db.add(user_message)
                db.flush()

            conversation.current_chapter_id = payload.chapter_id
            conversation.current_outline_node_id = outline_node_id
            conversation.model = payload.model
            if conversation.title == "新对话":
                conversation.title = _assistant_title_from_message(payload.message)
            conversation.updated_at = datetime.utcnow()

            assistant_message = AssistantMessage(
                conversation_id=conversation.id,
                role="assistant",
                content="正在规划需要调用哪些资料和角色AI...",
                status="running",
                payload_json=json.dumps({"tool_logs": []}, ensure_ascii=False),
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(conversation)
            db.refresh(user_message)
            db.refresh(assistant_message)

            history_text = _assistant_history_from_messages(
                db,
                conversation.id,
                before_message_id=user_message.id,
                limit=8,
            )
            if history_text == "暂无对话历史。":
                history_text = _assistant_history_text(payload.history)
            assistant_request = payload.message
            if payload.target_length:
                assistant_request = f"{assistant_request}\n\n如果需要生成正文，长度目标：约 {payload.target_length} 字。"

            yield _sse_event({
                "type": "conversation",
                "conversation": _assistant_conversation_to_dict(conversation),
                "user_message": _assistant_message_to_dict(user_message),
                "assistant_message": _assistant_message_to_dict(assistant_message),
            })

            yield _sse_event({"type": "status", "message": "正在规划需要调用的资料工具", "tool": "plan_tools"})
            planner_messages = [
                {
                    "role": "system",
                    "content": (
                        "你是小说写作助手的工具调度器。你要根据用户消息判断接下来需要读取哪些项目资料，"
                        "以及是否需要让角色AI参与扮演、是否可能创建新章节。只输出JSON对象。\n"
                        "可用工具：read_recent_summaries, read_outline, read_worldbuilding, read_characters, "
                        "read_relationships, read_chapter_detail, roleplay_characters。\n"
                        "输出格式：{\"intent\":\"advise|check|write|create_chapter|worldbuilding\","
                        "\"tools\":[\"read_recent_summaries\"],\"character_names\":[\"\"],"
                        "\"needs_worldbuilding\":false,\"should_create_chapter\":false,"
                        "\"chapter_title\":\"\",\"reason\":\"\"}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"作品：{project.title}\n"
                        f"当前章节：{selected_chapter.title if selected_chapter else '未选择'}\n"
                        f"对话历史：\n{history_text}\n\n"
                        f"用户需求：{assistant_request}"
                    ),
                },
            ]
            planner_error = None
            try:
                planner_result = await LLMGateway.chat_completion(
                    messages=planner_messages,
                    model=payload.model,
                    temperature=0.2,
                    max_tokens=1000,
                    retry=1,
                )
                plan = _normalize_assistant_plan(_parse_json_object(planner_result.get("content", "")), payload.message)
            except LLMError as exc:
                planner_error = str(exc)
                plan = _normalize_assistant_plan(None, payload.message)

            if planner_error:
                log = {"tool": "plan_tools", "status": "fallback", "detail": planner_error}
            else:
                log = {"tool": "plan_tools", "status": "ok", "detail": plan.get("reason")}
            tool_logs.append(log)
            yield _sse_event({"type": "tool", **log})

            summaries = _build_recent_summaries(db, project_id, payload.context_chapters)
            outline_ctx = _build_outline_context(db, project_id, outline_node_id)

            if "read_recent_summaries" in plan["tools"]:
                yield _sse_event({"type": "status", "message": "正在读取最近章节摘要", "tool": "read_recent_summaries"})
                context_sections.append(f"【前文摘要】\n{summaries}")
                log = {"tool": "read_recent_summaries", "status": "ok", "detail": f"最近 {payload.context_chapters} 章"}
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log})

            if "read_outline" in plan["tools"]:
                yield _sse_event({"type": "status", "message": "正在读取当前大纲和全局大纲", "tool": "read_outline"})
                outline_overview = _build_outline_overview(db, project_id)
                context_sections.append(f"【当前大纲节点】\n{outline_ctx}\n\n【全局大纲概览】\n{outline_overview}")
                log = {"tool": "read_outline", "status": "ok", "detail": "已读取当前节点和大纲概览"}
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log})

            if "read_worldbuilding" in plan["tools"]:
                yield _sse_event({"type": "status", "message": "正在读取世界观设定", "tool": "read_worldbuilding"})
                context_sections.append(f"【世界观设定】\n{_build_world_context(db, project_id, outline_node_id)}")
                log = {"tool": "read_worldbuilding", "status": "ok", "detail": "已读取世界观条目"}
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log})

            if "read_characters" in plan["tools"]:
                yield _sse_event({"type": "status", "message": "正在读取角色档案", "tool": "read_characters"})
                context_sections.append(f"【角色档案】\n{_build_character_catalog(db, project_id)}")
                log = {"tool": "read_characters", "status": "ok", "detail": "已读取角色档案"}
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log})

            if "read_relationships" in plan["tools"]:
                yield _sse_event({"type": "status", "message": "正在读取角色关系", "tool": "read_relationships"})
                context_sections.append(f"【角色关系】\n{_build_relationship_context(db, project_id)}")
                log = {"tool": "read_relationships", "status": "ok", "detail": "已读取角色关系"}
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log})

            if "read_chapter_detail" in plan["tools"]:
                yield _sse_event({"type": "status", "message": "正在读取当前章节和最近章节正文", "tool": "read_chapter_detail"})
                context_sections.append(
                    f"【当前章节正文】\n{_build_chapter_detail_context(db, project_id, payload.chapter_id)}\n\n"
                    f"【最近章节正文片段】\n{_build_recent_chapter_details(db, project_id)}"
                )
                log = {"tool": "read_chapter_detail", "status": "ok", "detail": "已读取当前章节和最近章节正文片段"}
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log})

            if history_text != "暂无对话历史。":
                context_sections.append(f"【对话历史与上一轮草稿】\n{history_text}")

            if "roleplay_characters" in plan["tools"]:
                roleplay_characters = _resolve_assistant_characters(
                    db,
                    project_id,
                    plan.get("character_names") or [],
                    outline_node_id,
                )
                for character in roleplay_characters:
                    yield _sse_event({
                        "type": "status",
                        "message": f"正在调用角色AI：{character.name}",
                        "tool": "roleplay_characters",
                    })
                    try:
                        result = await _assistant_character_roleplay(
                            db,
                            project_id,
                            character,
                            assistant_request,
                            outline_ctx,
                            summaries,
                            payload.model,
                        )
                        roleplay_results.append(result)
                        yield _sse_event({
                            "type": "tool",
                            "tool": "roleplay_characters",
                            "status": "ok",
                            "detail": f"{character.name}: {'行动' if result.get('should_act') else '旁观'}",
                        })
                    except LLMError as exc:
                        roleplay_results.append({
                            "character_id": character.id,
                            "character_name": character.name,
                            "should_act": False,
                            "action_type": "error",
                            "content": "",
                            "rationale": str(exc),
                        })
                        yield _sse_event({
                            "type": "tool",
                            "tool": "roleplay_characters",
                            "status": "error",
                            "detail": f"{character.name}: {exc}",
                        })
                context_sections.append(f"【角色AI扮演判断】\n{json.dumps(roleplay_results, ensure_ascii=False)}")
                log = {"tool": "roleplay_characters", "status": "ok", "detail": f"{len(roleplay_results)} 个角色"}
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log})

            if payload.auto_create_chapter and bool(plan.get("should_create_chapter")):
                placeholder_title = str(plan.get("chapter_title") or _chapter_title_from_request(payload.message) or "AI生成章节")
                yield _sse_event({
                    "type": "status",
                    "message": "正在创建章节草稿占位，正文完成后会自动写入",
                    "tool": "create_chapter",
                })
                draft_chapter = _create_assistant_chapter_placeholder(
                    db,
                    project_id,
                    placeholder_title,
                    outline_node_id,
                )
                db.commit()
                db.refresh(draft_chapter)
                log = {"tool": "create_chapter", "status": "running", "detail": f"已创建草稿占位：{draft_chapter.title}"}
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log, "chapter": _chapter_brief(draft_chapter)})
                yield _sse_event({"type": "draft_chapter", "chapter": _chapter_brief(draft_chapter)})

            final_messages = [
                {
                    "role": "system",
                    "content": (
                        "你是一个会使用项目资料的小说写作总控AI。你已经拿到了后端工具读取出的资料和角色AI扮演结果。"
                        "请完成用户需求：可以判断剧情是否合理、指出矛盾、建议补充世界观、预测后续发展，或生成可导入的新章节草稿。\n\n"
                        "要求：\n"
                        "1. 只基于给定资料推断，不要无依据改写既有设定。\n"
                        "2. 如果发现用户想写的剧情会破坏角色动机、时间线或世界观规则，要明确指出并给出改法。\n"
                        "3. 如果世界观缺口会影响剧情成立，在 worldbuilding_suggestions 中给出可直接导入的设定条目。\n"
                        "4. 如果角色AI判断某角色应行动，把这些行动自然合并进建议或章节草稿。\n"
                        "5. 如果用户要求创建/写新章节，chapter_draft.content 必须是完整正文草稿，不是大纲。\n"
                        "6. outline_node_id 必须从给定资料中【当前大纲节点】或【全局大纲概览】里显示的 [ID: xxx] 复制。如果资料中没有显示任何节点ID，或你不确定对应哪个节点，将 outline_node_id 设为空字符串 \"\"。严禁自行编造或猜测ID。\n"
                        "7. 只输出JSON对象。\n\n"
                        "输出格式：{\"reply\":\"给用户看的回答\","
                        "\"reasonableness\":\"reasonable|needs_revision|contradictory|unclear\","
                        "\"issues\":[\"\"],\"suggestions\":[\"\"],"
                        "\"worldbuilding_suggestions\":[{\"dimension\":\"geography|history|factions|power_system|races|culture\","
                        "\"title\":\"\",\"content\":\"\",\"reason\":\"\"}],"
                        "\"chapter_draft\":{\"should_create\":false,\"title\":\"\",\"content\":\"\",\"summary\":\"\","
                        "\"involved_characters\":[\"\"],\"outline_node_id\":\"\"}}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"作品：{project.title}\n"
                        f"简介：{project.description or '暂无'}\n"
                        f"写作风格：\n{_build_style_context(project)}\n\n"
                        f"工具计划：{json.dumps(plan, ensure_ascii=False)}\n\n"
                        f"{chr(10).join(context_sections)}\n\n"
                        f"用户需求：{assistant_request}"
                    ),
                },
            ]

            yield _sse_event({"type": "status", "message": "正在调用总控AI生成最终回复", "tool": "final_writer"})
            final_text = ""
            gen = LLMGateway.stream_chat_completion(
                messages=final_messages,
                model=payload.model,
                temperature=payload.temperature or 0.5,
                max_tokens=payload.max_tokens,
            )
            async for chunk in gen:
                final_text += chunk
                yield _sse_event({"type": "token", "content": chunk})

            parsed = _parse_json_object(final_text)
            if not parsed:
                parsed = {
                    "reply": final_text,
                    "reasonableness": "unclear",
                    "issues": [],
                    "suggestions": [],
                    "worldbuilding_suggestions": [],
                    "chapter_draft": {
                        "should_create": False,
                        "title": "",
                        "content": "",
                        "summary": "",
                        "involved_characters": [],
                    },
                }

            style_reports = await _repair_assistant_parsed_style(parsed, project, payload.model, payload.max_tokens)
            if style_reports:
                fixed_count = sum(1 for item in style_reports if item.get("fixed"))
                log = {
                    "tool": "style_guard",
                    "status": "ok" if fixed_count == len(style_reports) else "warning",
                    "detail": f"已检查禁用句式，修订 {fixed_count}/{len(style_reports)} 个字段",
                }
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log, "style_reports": style_reports})

            log = {"tool": "final_writer", "status": "ok", "detail": "最终回复已生成"}
            tool_logs.append(log)
            yield _sse_event({"type": "tool", **log})

            draft = parsed.get("chapter_draft") if isinstance(parsed.get("chapter_draft"), dict) else {}
            created_chapter = None
            should_create = payload.auto_create_chapter and (
                bool(draft.get("should_create")) or bool(plan.get("should_create_chapter"))
            )
            if should_create:
                yield _sse_event({"type": "status", "message": "正在写入章节正文和摘要", "tool": "create_chapter"})
                draft_title = str(draft.get("title") or plan.get("chapter_title") or _chapter_title_from_request(payload.message) or "AI生成章节")
                draft_content = str(draft.get("content") or "")
                draft_summary = str(draft.get("summary") or parsed.get("reply") or "")
                draft_character_names = [str(name) for name in (draft.get("involved_characters") or []) if name]
                target_outline_node_id = str(draft.get("outline_node_id") or outline_node_id or "") or None
                if draft_chapter and target_outline_node_id:
                    target_outline_node = _get_outline_node_or_404(db, project_id, target_outline_node_id)
                    draft_chapter.outline_node_id = target_outline_node.id if target_outline_node else None
                created = draft_chapter
                if created and draft_content.strip():
                    created = _finalize_assistant_chapter(
                        db,
                        created,
                        draft_title,
                        draft_content,
                        draft_summary,
                        draft_character_names,
                        payload.model,
                    )
                elif not created:
                    created = _create_assistant_chapter(
                        db,
                        project_id,
                        draft_title,
                        draft_content,
                        target_outline_node_id,
                        draft_summary,
                        draft_character_names,
                        payload.model,
                    )
                if created and draft_content.strip():
                    db.commit()
                    db.refresh(created)
                    draft_chapter_finalized = True
                    created_chapter = _chapter_brief(created)
                    log = {"tool": "create_chapter", "status": "ok", "detail": f"已写入章节：{created.title}"}
                else:
                    if draft_chapter:
                        db.delete(draft_chapter)
                        db.commit()
                    log = {"tool": "create_chapter", "status": "skipped", "detail": "草稿标题或正文为空"}
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log, "chapter": created_chapter})

            response_payload = {
                "reply": str(parsed.get("reply") or ""),
                "reasonableness": parsed.get("reasonableness") or "unclear",
                "issues": parsed.get("issues") if isinstance(parsed.get("issues"), list) else [],
                "suggestions": parsed.get("suggestions") if isinstance(parsed.get("suggestions"), list) else [],
                "worldbuilding_suggestions": (
                    parsed.get("worldbuilding_suggestions")
                    if isinstance(parsed.get("worldbuilding_suggestions"), list)
                    else []
                ),
                "chapter_draft": draft,
                "created_chapter": created_chapter,
                "plan": plan,
                "tool_logs": tool_logs,
                "roleplay_results": roleplay_results,
                "style_reports": style_reports,
                "model": payload.model,
                "usage": None,
            }
            assistant_message.content = response_payload["reply"] or "已完成分析。"
            assistant_message.payload_json = json.dumps(response_payload, ensure_ascii=False)
            assistant_message.status = "completed"
            assistant_message.updated_at = datetime.utcnow()
            conversation.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(assistant_message)
            db.refresh(conversation)
            response_payload["message"] = _assistant_message_to_dict(assistant_message)
            response_payload["conversation"] = _assistant_conversation_to_dict(conversation)

            yield _sse_event({
                "type": "complete",
                "data": response_payload,
            })
            yield _sse_event("[DONE]")
        except asyncio.CancelledError:
            if draft_chapter and not draft_chapter_finalized:
                db.delete(draft_chapter)
            if assistant_message:
                assistant_message.content = "已停止生成。"
                assistant_message.payload_json = json.dumps({"tool_logs": tool_logs}, ensure_ascii=False)
                assistant_message.status = "aborted"
                assistant_message.updated_at = datetime.utcnow()
                if conversation:
                    conversation.updated_at = datetime.utcnow()
                db.commit()
            raise
        except LLMError as exc:
            if draft_chapter and not draft_chapter_finalized:
                db.delete(draft_chapter)
            if assistant_message:
                assistant_message.content = str(exc)
                assistant_message.payload_json = json.dumps({"tool_logs": tool_logs}, ensure_ascii=False)
                assistant_message.status = "error"
                assistant_message.updated_at = datetime.utcnow()
                if conversation:
                    conversation.updated_at = datetime.utcnow()
                db.commit()
            yield _sse_event({"type": "error", "message": str(exc)})
            yield _sse_event("[DONE]")
        except Exception as exc:
            if draft_chapter and not draft_chapter_finalized:
                db.delete(draft_chapter)
            if assistant_message:
                assistant_message.content = f"服务器错误: {exc}"
                assistant_message.payload_json = json.dumps({"tool_logs": tool_logs}, ensure_ascii=False)
                assistant_message.status = "error"
                assistant_message.updated_at = datetime.utcnow()
                if conversation:
                    conversation.updated_at = datetime.utcnow()
                db.commit()
            yield _sse_event({"type": "error", "message": f"服务器错误: {exc}"})
            yield _sse_event("[DONE]")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/projects/{project_id}/ai/workspace-assistant/stream")
async def workspace_assistant_stream(
    project_id: str,
    payload: WorkspaceAssistantRequest,
    db: Session = Depends(get_db),
):
    """Conversational assistant for outline and character management with tool actions."""
    _get_project_or_404(db, project_id)

    async def event_generator():
        conversation = None
        user_message = None
        assistant_message = None
        tool_logs: list[dict] = []
        try:
            selected_node = _find_outline_by_title_or_id(db, project_id, payload.selected_outline_node_id)
            selected_character = (
                _find_character_by_name_or_id(db, project_id, payload.selected_character_id)
                if payload.selected_character_id
                else None
            )
            if payload.conversation_id:
                conversation = _get_assistant_conversation_or_404(db, project_id, payload.conversation_id)
                conversation.scope = payload.scope
            else:
                conversation = AssistantConversation(
                    project_id=project_id,
                    title=_assistant_title_from_message(payload.message),
                    scope=payload.scope,
                )
                db.add(conversation)
                db.flush()
            conversation.current_outline_node_id = selected_node.id if selected_node else None
            conversation.model = payload.model
            conversation.updated_at = datetime.utcnow()

            created_at = datetime.utcnow()
            user_message = AssistantMessage(
                conversation_id=conversation.id,
                role="user",
                content=payload.message,
                status="completed",
                created_at=created_at,
                updated_at=created_at,
            )
            assistant_message = AssistantMessage(
                conversation_id=conversation.id,
                role="assistant",
                content="正在读取项目资料...",
                status="running",
                payload_json=json.dumps({"tool_logs": []}, ensure_ascii=False),
                created_at=created_at + timedelta(microseconds=1),
                updated_at=created_at + timedelta(microseconds=1),
            )
            db.add(user_message)
            db.add(assistant_message)
            db.commit()
            db.refresh(conversation)
            db.refresh(user_message)
            db.refresh(assistant_message)

            yield _sse_event({
                "type": "conversation",
                "conversation": _assistant_conversation_to_dict(conversation),
                "user_message": _assistant_message_to_dict(user_message),
                "assistant_message": _assistant_message_to_dict(assistant_message),
            })

            yield _sse_event({"type": "status", "message": "正在读取大纲、角色、世界观和章节摘要", "tool": "read_project_context"})
            project = _get_project_or_404(db, project_id)
            selected_node = _find_outline_by_title_or_id(db, project_id, payload.selected_outline_node_id)
            selected_character = (
                _find_character_by_name_or_id(db, project_id, payload.selected_character_id)
                if payload.selected_character_id
                else None
            )
            outline_context = _build_outline_overview(db, project_id, limit=260)
            character_context = _build_character_catalog(db, project_id, limit=40)
            world_context = _build_world_context(db, project_id)
            style_context = _build_style_context(project)
            summaries = _build_recent_summaries(db, project_id, limit=8)
            selected_context = []
            if selected_node:
                selected_context.append(f"当前选中大纲：{json.dumps(_outline_node_payload(selected_node), ensure_ascii=False)}")
            if selected_character:
                selected_context.append(f"当前选中角色：{json.dumps(_character_payload(selected_character), ensure_ascii=False)}")
            log = {"tool": "read_project_context", "status": "ok", "detail": "已读取项目上下文"}
            tool_logs.append(log)
            yield _sse_event({"type": "tool", **log})

            history_text = _assistant_history_from_messages(db, conversation.id, before_message_id=user_message.id, limit=8)
            if history_text == "暂无对话历史。":
                history_text = _assistant_history_text(payload.history)

            available_tools = (
                "create_worldbuilding_entry, update_worldbuilding_entry, create_character, update_character, "
                "create_relationship, create_outline_node, update_outline_node, create_chapter"
            )
            scope_label_map = {
                "outline": "大纲规划",
                "characters": "角色管理",
                "worldbuilding": "世界观管理",
                "project": "项目规划",
            }
            scope_label = scope_label_map.get(payload.scope, "项目规划")
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"你是小说项目的{scope_label}AI助手。你可以和用户对话，也可以在用户明确要求创建、调整、生成时调用工具修改项目。\n"
                        f"可用工具：{available_tools}。\n"
                        "所有模块共用同一套项目工具：世界观、大纲、角色、关系和章节都可以互相读取、互相创建。\n"
                        "如果项目还没有世界观、角色或大纲，而用户要求从0开始写小说，你要先创建基础世界观、核心角色和前几个大纲节点，再建议或创建章节。\n"
                        "你必须先判断用户是想咨询还是想执行变更。只有用户明确说创建、修改、调整、生成、补全、关联、写入、从0开始时，actions 才能非空。\n"
                        "如果只是讨论，请 actions 输出空数组。\n\n"
                        "章节创建硬规则：如果用户要写新章节，但当前资料里没有能直接对应的章节大纲ID，第一轮不要创建章节、不要写入工具动作；"
                        "你必须先预测接下来大纲走向，按用户设置的连续规划章数给出大纲建议，并询问用户是否按这个方向发展。"
                        "只有用户明确确认后，才能先 create_outline_node / update_character / create_worldbuilding_entry，再 create_chapter。"
                        "如果用户否定方向，要询问接下来想怎么发展，等用户回答后再次给出大纲并询问。\n\n"
                        "工具参数格式：\n"
                        "- create_worldbuilding_entry: {\"dimension\":\"geography|history|factions|power_system|races|culture\",\"title\":\"\",\"content\":\"\",\"related_characters\":[\"可选\"],\"plot_usage\":\"可选\",\"constraints\":[\"可选\"],\"sort_order\":0}\n"
                        "- update_worldbuilding_entry: {\"id\":\"条目ID或标题\",\"dimension\":\"可选\",\"title\":\"可选\",\"content\":\"可选\",\"sort_order\":0}\n"
                        "- create_outline_node: {\"parent_id\":\"可空\",\"node_type\":\"volume|chapter|section\",\"title\":\"\",\"summary\":\"\",\"status\":\"pending|in_progress|completed\",\"character_names\":[\"\"]}\n"
                        "- update_outline_node: {\"id\":\"大纲ID\",\"title\":\"可选\",\"summary\":\"可选\",\"status\":\"可选\",\"character_names\":[\"可选\"]}\n"
                        "- create_character: {\"name\":\"\",\"appearance\":\"\",\"personality\":\"\",\"background\":\"\",\"abilities\":[\"\"],\"role_type\":\"protagonist|supporting|antagonist|mentor|other\"}\n"
                        "- update_character: {\"id\":\"角色ID或角色名\",\"appearance\":\"可选\",\"personality\":\"可选\",\"background\":\"可选\",\"abilities\":[\"可选\"],\"role_type\":\"可选\"}\n"
                        "- create_relationship: {\"source\":\"角色名或ID\",\"target\":\"角色名或ID\",\"relationship_type\":\"\",\"description\":\"\"}\n"
                        "- create_chapter: {\"title\":\"\",\"content\":\"完整正文\",\"outline_node_id\":\"从大纲列表中的 [ID] 复制，不确定则为空字符串\",\"outline_node_title\":\"刚创建或已有的大纲标题，可选\",\"summary\":\"可选\",\"involved_characters\":[\"\"]}\n\n"
                        "重要：outline_node_id、character id 等标识符必须从下方给定资料中直接复制，严禁自行编造。如果资料中没有明确的ID，请留空或使用角色名称匹配。\n\n"
                        "创建顺序建议：从0建书时先 worldbuilding，再 characters/relationships，再 outline；写正文时先核对大纲、角色和世界观，再 create_chapter。\n"
                        "只输出合法JSON对象，不要Markdown。格式："
                        "{\"reply\":\"给用户看的回复\",\"actions\":[{\"tool\":\"工具名\",\"arguments\":{}}],\"needs_confirmation\":false}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"作品：{project.title}\n"
                        f"简介：{project.description or '暂无'}\n"
                        f"写作风格与禁用表达：\n{style_context}\n\n"
                        f"对话历史：\n{history_text}\n\n"
                        f"{chr(10).join(selected_context) or '当前没有选中对象。'}\n\n"
                        f"大纲：\n{outline_context}\n\n"
                        f"角色：\n{character_context}\n\n"
                        f"世界观：\n{world_context}\n\n"
                        f"最近章节摘要：\n{summaries}\n\n"
                        f"用户设置：连续规划章数={payload.outline_batch_count}；自动执行工具={payload.auto_apply}。\n\n"
                        f"用户需求：{payload.message}"
                    ),
                },
            ]

            yield _sse_event({"type": "status", "message": "正在让模型决定是否调用工具", "tool": "planner"})
            result = await LLMGateway.chat_completion(
                messages=messages,
                model=payload.model,
                temperature=payload.temperature or 0.3,
                max_tokens=payload.max_tokens,
                retry=1,
            )
            parsed = _parse_json_object(result.get("content", "")) or {
                "reply": result.get("content", ""),
                "actions": [],
                "needs_confirmation": False,
            }
            actions = parsed.get("actions") if isinstance(parsed.get("actions"), list) else []
            if _chapter_action_needs_outline_confirmation(db, project_id, actions, payload.message):
                actions = []
                parsed["actions"] = []
                parsed["needs_confirmation"] = True
                reply = str(parsed.get("reply") or "").strip()
                if "是否" not in reply and "确认" not in reply:
                    reply = (
                        f"{reply}\n\n" if reply else ""
                    ) + f"我会先按接下来 {payload.outline_batch_count} 章给出大纲方向，请你确认是否按这个方向发展；确认后我再写入大纲、角色/世界观变更，并创建新章节。"
                parsed["reply"] = reply
            log = {"tool": "planner", "status": "ok", "detail": f"模型提出 {len(actions)} 个工具动作"}
            tool_logs.append(log)
            yield _sse_event({"type": "tool", **log})

            applied_actions = []
            if payload.auto_apply and actions:
                for action in actions[:12]:
                    if not isinstance(action, dict):
                        continue
                    tool = str(action.get("tool") or "tool")
                    yield _sse_event({"type": "status", "message": f"正在执行工具：{tool}", "tool": tool})
                    try:
                        action_result = _execute_workspace_action(db, project_id, action)
                    except Exception as exc:
                        action_result = {"tool": tool, "status": "error", "detail": str(exc)}
                    applied_actions.append(action_result)
                    tool_logs.append({
                        "tool": action_result.get("tool") or tool,
                        "status": action_result.get("status") or "ok",
                        "detail": action_result.get("detail") or "",
                    })
                    yield _sse_event({"type": "tool", **tool_logs[-1]})
                db.commit()
            elif actions:
                log = {"tool": "auto_apply", "status": "skipped", "detail": "自动执行已关闭"}
                tool_logs.append(log)
                yield _sse_event({"type": "tool", **log})

            response_payload = {
                "reply": str(parsed.get("reply") or "已完成。"),
                "actions": actions,
                "applied_actions": applied_actions,
                "tool_logs": tool_logs,
                "scope": payload.scope,
                "model": result.get("model"),
                "usage": result.get("usage"),
            }
            assistant_message.content = response_payload["reply"]
            assistant_message.payload_json = json.dumps(response_payload, ensure_ascii=False)
            assistant_message.status = "completed"
            assistant_message.updated_at = datetime.utcnow()
            conversation.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(assistant_message)
            db.refresh(conversation)
            response_payload["message"] = _assistant_message_to_dict(assistant_message)
            response_payload["conversation"] = _assistant_conversation_to_dict(conversation)
            yield _sse_event({"type": "complete", "data": response_payload})
            yield _sse_event("[DONE]")
        except LLMError as exc:
            if assistant_message:
                assistant_message.content = str(exc)
                assistant_message.status = "error"
                assistant_message.payload_json = json.dumps({"tool_logs": tool_logs}, ensure_ascii=False)
                db.commit()
            yield _sse_event({"type": "error", "message": str(exc)})
            yield _sse_event("[DONE]")
        except Exception as exc:
            if assistant_message:
                assistant_message.content = f"服务器错误: {exc}"
                assistant_message.status = "error"
                assistant_message.payload_json = json.dumps({"tool_logs": tool_logs}, ensure_ascii=False)
                db.commit()
            yield _sse_event({"type": "error", "message": f"服务器错误: {exc}"})
            yield _sse_event("[DONE]")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Character change detection after chapter
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/ai/character-changes/{chapter_id}")
async def detect_character_changes(
    project_id: str,
    chapter_id: str,
    payload: CharacterChangesRequest,
    db: Session = Depends(get_db),
):
    _get_project_or_404(db, project_id)
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id, Chapter.project_id == project_id).first()
    if not chapter:
        raise NotFoundError("章节不存在")

    characters = (
        db.query(Character)
        .filter(Character.project_id == project_id, Character.is_evolution_tracked == True)
        .all()
    )
    if not characters:
        return ApiResponse.success(data={"changes": [], "total": 0}, message="没有开启追踪的角色")

    character_by_id = {c.id: c for c in characters}
    char_payload = [
        {
            "id": c.id,
            "name": c.name,
            "personality": c.personality,
            "abilities": c.abilities,
            "background": c.background,
            "role_type": c.role_type,
        }
        for c in characters
    ]

    chapter_text = chapter.content or ""
    if len(chapter_text) > 8000:
        chapter_text = chapter_text[:8000] + "\n...(后续内容已截断)"

    messages = [
        {
            "role": "system",
            "content": (
                "你是一位小说角色设定追踪编辑，专精于检测角色在剧情推进中发生的可记录变化。你理解角色弧光理论——角色应随着经历而成长、改变或恶化。\n\n"
                "【任务】\n"
                "分析新章节内容，对比当前角色档案，检测每个角色发生的所有可记录变化。\n\n"
                "【变化类型定义与判断标准】\n"
                "- skill（技能/能力变化）：角色习得新技能、失去旧能力、能力显著增强或减弱。判断标准：原文明确描写了学习/失去/变化的过程或结果。\n"
                "- experience（重要经历）：角色经历了改变其认知、地位或命运的重大事件。判断标准：该事件在原文中有明确的因果影响或情感冲击。\n"
                "- relationship（关系变化）：角色与他人的关系发生了实质性改变——从陌生到熟悉、从友好到敌对、从平等变为从属等。判断标准：原文中有关系状态转变的具体描写。\n"
                "- personality（性格成长）：角色的性格特征发生了可观察的演变——变得勇敢/懦弱、开朗/阴郁、果断/犹豫等。判断标准：角色的言行模式与旧档案描述有显著差异，且不是临时情绪反应。\n\n"
                "【检测精度要求】\n"
                "1. 区分永久变化与临时状态：角色因醉酒、被控制、极度恐惧等短暂状态下的行为改变不算性格变化。\n"
                "2. 区分显性变化与隐性变化：有些变化是角色自己意识到的（显性），有些是读者能感知但角色尚未意识到的（隐性）。两种都应检测。\n"
                "3. confidence 判断标准：\n"
                "   - high：原文有明确语句支持该变化（如「从那以后，他变得...」、「他终于学会了...」）\n"
                "   - medium：原文暗示了变化但未明说（多个场景表现出与旧档案不同的行为模式）\n"
                "   - low：仅有模糊迹象，可能只是暂时状态或解读偏差\n"
                "4. old_value 应从当前角色档案中提取对应字段的值，new_value 应从原文中提取具体描述。若旧档案中对应字段为空，old_value 填写「（档案中无记录）」。\n\n"
                "【禁止事项】\n"
                "- 禁止为没有发生变化的角色强行编造变化。无变化就输出空数组 []。\n"
                "- 禁止将临时情绪波动标记为性格变化。\n"
                "- 禁止将原文中未发生的事情标记为变化。\n"
                "- 禁止输出JSON数组以外的任何内容。\n\n"
                "【输出格式】\n"
                "只输出JSON数组：\n"
                "[{\"character_id\":\"\",\"character_name\":\"\",\"change_type\":\"skill|experience|relationship|personality\","
                "\"field_name\":\"\",\"old_value\":\"\",\"new_value\":\"\",\"confidence\":\"high|medium|low\"}]\n"
                "如果没有明显变化，输出 []。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"章节标题：{chapter.title}\n"
                f"章节内容：\n{chapter_text}\n\n"
                f"当前角色档案：\n{json.dumps(char_payload, ensure_ascii=False)}"
            ),
        },
    ]
    result = await LLMGateway.chat_completion(
        messages=messages,
        model=payload.model,
        temperature=payload.temperature or 0.3,
    )

    changes_text = result.get("content", "")
    changes = []
    try:
        changes = json.loads(changes_text.strip().removeprefix("```json").removesuffix("```").strip())
    except json.JSONDecodeError:
        pass

    # Persist detected changes
    saved_changes = []
    touched_character_ids: set[str] = set()
    allowed_change_types = {"skill", "experience", "relationship", "personality"}
    default_field_by_type = {
        "skill": "abilities",
        "experience": "background",
        "relationship": "background",
        "personality": "personality",
    }
    allowed_fields = {"abilities", "personality", "background", "appearance"}
    timeline_type_by_change = {
        "skill": "skill_gain",
        "experience": "key_decision",
        "relationship": "relationship_change",
        "personality": "emotional_turning_point",
    }
    if isinstance(changes, list):
        for change in changes:
            if not isinstance(change, dict):
                continue
            char_id = str(change.get("character_id", "")).strip()
            if char_id not in character_by_id:
                continue
            change_type = str(change.get("change_type", "experience")).strip()
            if change_type not in allowed_change_types:
                change_type = "experience"
            field_name = str(change.get("field_name") or default_field_by_type[change_type]).strip()
            if field_name not in allowed_fields:
                field_name = default_field_by_type[change_type]
            old_val = str(change.get("old_value", ""))[:2000] if change.get("old_value") else None
            new_val = str(change.get("new_value", ""))[:2000] if change.get("new_value") else None

            log = CharacterChangeLog(
                character_id=char_id,
                chapter_id=chapter_id,
                change_type=change_type,
                field_name=field_name,
                old_value=old_val,
                new_value=new_val,
                confirmed=False,
            )
            db.add(log)

            if char_id not in touched_character_ids:
                exists = (
                    db.query(ChapterCharacter)
                    .filter(
                        ChapterCharacter.chapter_id == chapter_id,
                        ChapterCharacter.character_id == char_id,
                    )
                    .first()
                )
                if not exists:
                    db.add(ChapterCharacter(
                        chapter_id=chapter_id,
                        character_id=char_id,
                        appearance_type="出场",
                        description="AI角色演进检测识别到该角色在本章发生变化",
                    ))
                touched_character_ids.add(char_id)

            db.add(CharacterTimeline(
                character_id=char_id,
                chapter_id=chapter_id,
                event_description=new_val or f"{change.get('character_name', '')}发生{change_type}变化",
                event_type=timeline_type_by_change[change_type],
                emotional_state_change=new_val if change_type == "personality" else None,
            ))
            saved_changes.append({
                "character_id": char_id,
                "character_name": character_by_id[char_id].name,
                "change_type": change_type,
                "field_name": field_name,
                "old_value": old_val,
                "new_value": new_val,
                "confidence": change.get("confidence", "medium"),
            })

    db.commit()
    return ApiResponse.success(
        data={"changes": saved_changes, "total": len(saved_changes)},
        message=f"检测到 {len(saved_changes)} 处角色变化",
    )
