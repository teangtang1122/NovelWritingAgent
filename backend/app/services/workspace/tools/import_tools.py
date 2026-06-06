"""Import workspace tools for text-based chapter ingestion."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ....schemas.importer import ImportSplitSuggestion
from ....services.import_service import build_split_preview, execute_import


def _split_from_dict(item: object) -> ImportSplitSuggestion | None:
    if isinstance(item, ImportSplitSuggestion):
        return item
    if not isinstance(item, dict):
        return None
    try:
        return ImportSplitSuggestion(**item)
    except Exception:
        return None


async def preview_import_splits(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    text = str(args.get("text") or "")
    if len(text.strip()) < 100:
        return {"tool": "preview_import_splits", "status": "skipped", "detail": "导入文本太短，至少需要 100 个字符"}
    splits, method, needs_review, failed_blocks = await build_split_preview(text, args.get("model"))
    return {
        "tool": "preview_import_splits",
        "status": "ok",
        "detail": f"识别到 {len(splits)} 个章节切分点",
        "data": {
            "splits": splits,
            "total": len(splits),
            "method": method,
            "needs_review": needs_review,
            "failed_blocks": failed_blocks,
        },
    }


async def import_text_as_chapters(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    text = str(args.get("text") or "")
    if not text.strip():
        return {"tool": "import_text_as_chapters", "status": "skipped", "detail": "导入文本为空"}

    raw_splits = args.get("splits") if isinstance(args.get("splits"), list) else []
    splits = [_split_from_dict(item) for item in raw_splits]
    splits = [item for item in splits if item is not None]
    if not splits and bool(args.get("auto_split", True)) and len(text.strip()) >= 100:
        preview, _method, _needs_review, _failed_blocks = await build_split_preview(text, args.get("model"))
        splits = [_split_from_dict(item) for item in preview]
        splits = [item for item in splits if item is not None]

    chapters = execute_import(db, project_id, text, splits, str(args.get("outline_node_id") or "") or None)
    db.flush()
    return {
        "tool": "import_text_as_chapters",
        "status": "ok",
        "detail": f"已导入 {len(chapters)} 个章节",
        "data": {"chapters": chapters, "total": len(chapters)},
    }
