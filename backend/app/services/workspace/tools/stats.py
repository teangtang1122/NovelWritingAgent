"""Statistics workspace tools."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ....database.models import Chapter, Project


async def get_today_writing_stats(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"tool": "get_today_writing_stats", "status": "skipped", "detail": "作品不存在"}
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = today_start + timedelta(days=1)
    row = (
        db.query(
            func.coalesce(func.sum(Chapter.word_count), 0).label("total_words"),
            func.count(Chapter.id).label("chapters_count"),
        )
        .filter(
            Chapter.project_id == project_id,
            Chapter.created_at >= today_start,
            Chapter.created_at < today_end,
        )
        .one()
    )
    today_words = int(row.total_words)
    goal = project.daily_word_goal or 6000
    progress = round((today_words / goal) * 100, 1) if goal > 0 else 0
    return {
        "tool": "get_today_writing_stats",
        "status": "ok",
        "detail": f"今日写作 {today_words} 字，目标 {goal} 字",
        "data": {
            "date": today.isoformat(),
            "total_words": today_words,
            "daily_goal": goal,
            "progress_percent": min(progress, 100.0),
            "chapters_written": int(row.chapters_count),
        },
    }


async def get_writing_stats_history(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    days = max(1, min(365, int(args.get("days") or 7)))
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"tool": "get_writing_stats_history", "status": "skipped", "detail": "作品不存在"}
    start_date = date.today() - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())
    rows = (
        db.query(
            func.date(Chapter.created_at).label("day"),
            func.coalesce(func.sum(Chapter.word_count), 0).label("total_words"),
        )
        .filter(
            Chapter.project_id == project_id,
            Chapter.created_at >= start_dt,
        )
        .group_by(func.date(Chapter.created_at))
        .all()
    )
    words_by_date = {str(r.day): int(r.total_words) for r in rows}
    goal = project.daily_word_goal or 6000
    items = []
    total_words = 0
    current = start_date
    while current <= date.today():
        words = words_by_date.get(current.isoformat(), 0)
        total_words += words
        items.append({"date": current.isoformat(), "total_words": words, "daily_goal": goal})
        current += timedelta(days=1)
    return {
        "tool": "get_writing_stats_history",
        "status": "ok",
        "detail": f"近 {days} 天共写作 {total_words} 字",
        "data": {
            "items": items,
            "total_days": len(items),
            "total_words": total_words,
            "average_words_per_day": round(total_words / max(len(items), 1), 1),
        },
    }


async def set_daily_word_goal(db: Session, project_id: str, args: dict[str, Any]) -> dict:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"tool": "set_daily_word_goal", "status": "skipped", "detail": "作品不存在"}
    goal = max(0, int(args.get("daily_word_goal") or args.get("goal") or 0))
    project.daily_word_goal = goal
    db.flush()
    return {"tool": "set_daily_word_goal", "status": "ok", "detail": f"每日目标已更新为 {goal} 字", "data": {"daily_word_goal": goal}}
