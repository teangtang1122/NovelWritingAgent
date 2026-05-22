"""Pydantic schemas for writing statistics."""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class TodayStats(BaseModel):
    """Today's writing statistics."""
    date: date
    total_words: int
    daily_goal: int
    progress_percent: float
    chapters_written: int


class DailyStatsItem(BaseModel):
    """Single day writing record."""
    date: date
    total_words: int
    daily_goal: int


class StatsHistoryResponse(BaseModel):
    """Historical writing statistics."""
    items: list[DailyStatsItem]
    total_days: int
    total_words: int
    average_words_per_day: float


class GoalUpdate(BaseModel):
    """Update daily word goal."""
    daily_word_goal: int = Field(..., ge=0, description="Daily word count target")
