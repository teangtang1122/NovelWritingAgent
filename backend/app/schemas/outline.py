"""Pydantic schemas for outline planning."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


OutlineNodeType = Literal["volume", "chapter", "section"]
OutlineStatus = Literal["pending", "in_progress", "completed"]


class OutlineCharacterLinkInput(BaseModel):
    """Character linked to an outline node."""

    character_id: str = Field(..., description="Character ID")
    role_in_scene: Optional[str] = Field(None, max_length=50, description="Role in this outline node")


class OutlineNodeCreate(BaseModel):
    """Schema for creating an outline node."""

    parent_id: Optional[str] = Field(None, description="Parent outline node ID")
    node_type: OutlineNodeType = Field(..., description="volume/chapter/section")
    title: str = Field(..., min_length=1, max_length=200)
    summary: Optional[str] = None
    status: OutlineStatus = "pending"
    sort_order: int = Field(0, ge=0)
    character_ids: list[str] = Field(default_factory=list)
    characters: Optional[list[OutlineCharacterLinkInput]] = None


class OutlineNodeUpdate(BaseModel):
    """Schema for updating an outline node."""

    parent_id: Optional[str] = None
    node_type: Optional[OutlineNodeType] = None
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    summary: Optional[str] = None
    status: Optional[OutlineStatus] = None
    sort_order: Optional[int] = Field(None, ge=0)
    character_ids: Optional[list[str]] = None
    characters: Optional[list[OutlineCharacterLinkInput]] = None


class OutlineReorderItem(BaseModel):
    """Single outline node reorder operation."""

    id: str
    parent_id: Optional[str] = None
    sort_order: int = Field(0, ge=0)


class OutlineReorderRequest(BaseModel):
    """Schema for reordering outline nodes.

    The API accepts either a list of explicit items, or a parent_id plus
    sort_order list for replacing one sibling group's order.
    """

    items: list[OutlineReorderItem] = Field(default_factory=list)
    parent_id: Optional[str] = None
    sort_order: Optional[list[str]] = None


class OutlineAISuggestRequest(BaseModel):
    """Schema for AI-assisted outline summary suggestion."""

    node_id: Optional[str] = Field(None, description="Target outline node ID")
    prompt: Optional[str] = Field(None, max_length=2000, description="Author instruction")
    suggestion_count: int = Field(1, ge=1, le=8, description="Number of continuous outline nodes to suggest")
    model: Optional[str] = Field(None, description="Optional model identifier")


class LinkedCharacterResponse(BaseModel):
    """Character information linked to an outline node."""

    id: str
    name: str
    role_type: Optional[str]
    role_in_scene: Optional[str]


class OutlineNodeResponse(BaseModel):
    """Outline node response."""

    id: str
    project_id: str
    parent_id: Optional[str]
    node_type: str
    title: str
    summary: Optional[str]
    status: str
    sort_order: int
    linked_characters: list[LinkedCharacterResponse]
    children: list["OutlineNodeResponse"] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


OutlineNodeResponse.model_rebuild()
