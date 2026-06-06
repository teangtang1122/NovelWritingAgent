"""Export workspace tools."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...export_service import _generate_docx, _generate_export_content, _generate_pdf, _ordered_chapters, _store_export_file


async def export_project(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    scope = str(args.get("scope") or "all")
    fmt = str(args.get("format") or "txt").lower()
    valid_scopes = {"chapters", "outline", "characters", "worldbuilding", "all", "single", "selected"}
    valid_formats = {"txt", "docx", "pdf"}
    if scope not in valid_scopes:
        return {"tool": "export_project", "status": "skipped", "detail": f"无效导出范围：{scope}"}
    if fmt not in valid_formats:
        return {"tool": "export_project", "status": "skipped", "detail": f"无效导出格式：{fmt}"}

    chapter_ids = args.get("chapter_ids") if isinstance(args.get("chapter_ids"), list) else []
    include_outline = bool(args.get("include_outline") or False)
    include_characters = bool(args.get("include_characters") or False)
    include_worldbuilding = bool(args.get("include_worldbuilding") or False)

    if fmt == "pdf":
        filename, buf = _generate_pdf(
            db,
            project_id,
            scope,
            chapter_ids=chapter_ids,
            include_outline=include_outline,
            include_characters=include_characters,
            include_worldbuilding=include_worldbuilding,
        )
        metadata = _store_export_file(project_id, filename, buf.getvalue(), "application/pdf", fmt)
    elif fmt == "docx":
        filename, buf = _generate_docx(
            db,
            project_id,
            scope,
            chapter_ids=chapter_ids,
            include_outline=include_outline,
            include_characters=include_characters,
            include_worldbuilding=include_worldbuilding,
        )
        metadata = _store_export_file(
            project_id,
            filename,
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            fmt,
        )
    else:
        filename, content = _generate_export_content(
            db,
            project_id,
            scope,
            chapter_ids=chapter_ids,
            include_outline=include_outline,
            include_characters=include_characters,
            include_worldbuilding=include_worldbuilding,
        )
        metadata = _store_export_file(project_id, filename, content.encode("utf-8"), "text/plain; charset=utf-8", fmt)

    return {
        "tool": "export_project",
        "status": "ok",
        "detail": f"已生成导出文件：{metadata.get('filename')}",
        "data": metadata,
    }


async def get_export_word_count(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    chapters = _ordered_chapters(db, project_id)
    items = [
        {
            "id": chapter.id,
            "title": chapter.title,
            "word_count": chapter.word_count or 0,
            "version": chapter.current_version or 1,
        }
        for chapter in chapters
    ]
    total_words = sum(item["word_count"] for item in items)
    return {
        "tool": "get_export_word_count",
        "status": "ok",
        "detail": f"共 {len(items)} 章，{total_words} 字",
        "data": {"chapters": items, "total_chapters": len(items), "total_words": total_words},
    }
