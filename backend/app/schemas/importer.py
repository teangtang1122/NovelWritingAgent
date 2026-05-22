"""Pydantic schemas for file import."""
from typing import Optional
from pydantic import BaseModel, Field


class ImportSplitSuggestion(BaseModel):
    """A single suggested chapter split point."""
    title: str
    start_char: int
    end_char: int
    preview: str
    needs_review: bool = False
    review_reason: Optional[str] = None
    source: Optional[str] = None
    block_index: Optional[int] = None


class ImportSplitRequest(BaseModel):
    """Request to detect chapter boundaries in imported text."""
    text: str = Field(..., min_length=100)
    model: Optional[str] = Field(None)


class ConfirmImportRequest(BaseModel):
    """Request to save imported text as chapters."""
    text: str = Field(..., min_length=1)
    splits: list[ImportSplitSuggestion] = Field(default_factory=list)
    outline_node_id: Optional[str] = Field(None)
