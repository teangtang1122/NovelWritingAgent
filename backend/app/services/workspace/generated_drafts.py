"""Short-lived generated draft cache for workspace tools.

The assistant model should not have to copy a full chapter body back into a
tool-call argument. Tool-call arguments are a common place for long text to get
truncated, so writers store the full text here and write tools can resolve it by
draft id or by matching a provided prefix.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from typing import Any
from uuid import uuid4

MAX_CHAPTER_DRAFTS = 64

_CHAPTER_DRAFTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def store_chapter_draft(
    *,
    project_id: str,
    content: str,
    title: str = "",
    outline_node_id: str | None = None,
) -> str:
    draft_id = str(uuid4())
    _CHAPTER_DRAFTS[draft_id] = {
        "project_id": project_id,
        "title": title,
        "outline_node_id": outline_node_id or "",
        "content": content,
        "created_at": datetime.utcnow(),
    }
    _CHAPTER_DRAFTS.move_to_end(draft_id)
    while len(_CHAPTER_DRAFTS) > MAX_CHAPTER_DRAFTS:
        _CHAPTER_DRAFTS.popitem(last=False)
    return draft_id


def get_chapter_draft(project_id: str, draft_id: str | None) -> str | None:
    if not draft_id:
        return None
    entry = _CHAPTER_DRAFTS.get(str(draft_id))
    if not entry or entry.get("project_id") != project_id:
        return None
    _CHAPTER_DRAFTS.move_to_end(str(draft_id))
    return str(entry.get("content") or "")


def _looks_like_prefix(prefix: str, full: str) -> bool:
    prefix = prefix.strip()
    full = full.strip()
    if not prefix:
        return True
    if len(full) <= len(prefix):
        return False
    head = full[: max(200, min(len(prefix), 1200))]
    return head.startswith(prefix[: len(head)]) or prefix[:200] in full[:1200]


def resolve_chapter_draft_content(
    *,
    project_id: str,
    provided_content: str = "",
    draft_id: str | None = None,
    outline_node_id: str | None = None,
) -> str:
    """Return the best full chapter content for a write/evaluation action."""
    provided = provided_content or ""
    direct = get_chapter_draft(project_id, draft_id)
    if direct and len(direct.strip()) > len(provided.strip()):
        return direct

    outline_id = str(outline_node_id or "").strip()
    for _id, entry in reversed(_CHAPTER_DRAFTS.items()):
        if entry.get("project_id") != project_id:
            continue
        if outline_id and str(entry.get("outline_node_id") or "") != outline_id:
            continue
        content = str(entry.get("content") or "")
        if content and _looks_like_prefix(provided, content):
            return content

    return provided

