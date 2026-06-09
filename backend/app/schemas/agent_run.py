"""Pydantic schemas for external Agent runs and events."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


class AgentRunCreate(BaseModel):
    """Schema for creating a new Agent run."""
    source: str = Field(default="mcp", description="Source: mcp or internal")
    client_name: Optional[str] = Field(default=None, description="Client name: claude-code, codex, etc.")
    title: Optional[str] = Field(default=None, description="Run title")


class AgentRunRead(BaseModel):
    """Schema for reading an Agent run."""
    id: str
    project_id: str
    source: str
    client_name: Optional[str] = None
    title: Optional[str] = None
    status: str
    current_step: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentRunEventCreate(BaseModel):
    """Schema for creating an Agent run event."""
    event_type: str = Field(..., description="Event type")
    status: str = Field(default="ok", description="Event status")
    message: Optional[str] = Field(default=None, description="Event message")
    payload_json: Optional[str] = Field(default=None, description="JSON payload")


class AgentRunEventRead(BaseModel):
    """Schema for reading an Agent run event."""
    id: str
    run_id: str
    sequence: int
    event_type: str
    status: str
    message: Optional[str] = None
    payload_json: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentRunListResponse(BaseModel):
    """Response for listing Agent runs."""
    items: list[AgentRunRead]
    total: int


class AgentRunEventListResponse(BaseModel):
    """Response for listing Agent run events."""
    items: list[AgentRunEventRead]
    total: int
