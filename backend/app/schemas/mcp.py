"""Pydantic schemas for MCP server configuration."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class McpServerConfigBase(BaseModel):
    """Base schema for MCP server config."""
    name: str = Field(..., min_length=1, max_length=100, description="Server name")
    transport: str = Field(default="stdio", description="Transport: stdio or http")
    command: Optional[str] = Field(default=None, description="Command for stdio transport")
    url: Optional[str] = Field(default=None, description="URL for http transport")
    enabled: bool = Field(default=True, description="Whether the server is enabled")


class McpServerConfigCreate(McpServerConfigBase):
    """Schema for creating an MCP server config."""
    pass


class McpServerConfigUpdate(BaseModel):
    """Schema for updating an MCP server config."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    transport: Optional[str] = None
    command: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None


class McpServerConfigRead(McpServerConfigBase):
    """Schema for reading an MCP server config."""
    id: str
    project_id: str
    status: str
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
