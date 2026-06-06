"""Pydantic schemas for the scheduler API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScheduledTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    prompt: str = Field(..., min_length=1)
    cron_expr: str | None = None
    interval_minutes: int | None = Field(None, ge=1)
    tool_policy: list[str] = Field(default_factory=list)


class ScheduledTaskUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    prompt: str | None = None
    cron_expr: str | None = None
    interval_minutes: int | None = Field(None, ge=1)
    tool_policy: list[str] | None = None
    status: str | None = None


class ScheduledTaskResponse(BaseModel):
    id: str
    project_id: str
    name: str
    prompt: str
    cron_expr: str | None = None
    interval_minutes: int | None = None
    tool_policy: list[str] = Field(default_factory=list)
    status: str
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    last_run_output: str | None = None
    next_run_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScheduledTaskListResponse(BaseModel):
    items: list[ScheduledTaskResponse]
    total: int


class ScheduledTaskRunResponse(BaseModel):
    task_id: str
    status: str
    output: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
