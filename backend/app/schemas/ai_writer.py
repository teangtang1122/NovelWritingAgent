"""Pydantic schemas for AI writing engine endpoints."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class NarratorGenerateRequest(BaseModel):
    """Request for narrator AI text generation."""
    prompt: str = Field(..., min_length=1, description="User instruction for the narrator")
    chapter_id: Optional[str] = Field(None, description="Current chapter context")
    outline_node_id: Optional[str] = Field(None, description="Current outline node for scene context")
    model: Optional[str] = Field(None, description="Model override")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    context_chapters: int = Field(5, ge=0, le=20, description="Number of recent chapter summaries to include")


class CharacterDialogueRequest(BaseModel):
    """Request for character AI dialogue generation."""
    prompt: str = Field(..., min_length=1, description="Scene context or dialogue direction")
    chapter_id: Optional[str] = Field(None, description="Current chapter context")
    outline_node_id: Optional[str] = Field(None, description="Current outline node")
    model: Optional[str] = Field(None, description="Model override (overrides character config)")
    temperature: Optional[float] = Field(0.8, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    context_chapters: int = Field(5, ge=0, le=20)


class DialogueBattleRequest(BaseModel):
    """Request for multi-character dialogue battle mode."""
    prompt: str = Field(..., min_length=1, description="Scene description and dialogue direction")
    character_ids: list[str] = Field(..., min_items=1, max_items=5, description="Participating character IDs in order")
    chapter_id: Optional[str] = Field(None)
    outline_node_id: Optional[str] = Field(None)
    turns: int = Field(3, ge=1, le=10, description="Number of dialogue rounds")
    model: Optional[str] = Field(None, description="Model override for all characters")
    temperature: Optional[float] = Field(0.8, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    context_chapters: int = Field(5, ge=0, le=20)


class RewriteRequest(BaseModel):
    """Request for rewriting selected text."""
    text: str = Field(..., min_length=1, description="Original text to rewrite")
    style: Optional[str] = Field(None, description="Target style: vivid/concise/serious/humorous/poetic")
    prompt: Optional[str] = Field(None, description="Additional rewrite instructions")
    model: Optional[str] = Field(None)
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)


class ExpandRequest(BaseModel):
    """Request for expanding selected text."""
    text: str = Field(..., min_length=1, description="Original text to expand")
    prompt: Optional[str] = Field(None, description="What to expand on")
    model: Optional[str] = Field(None)
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)


class ContinueRequest(BaseModel):
    """Request for continuing from selected text."""
    text: str = Field(..., min_length=1, description="Text to continue from")
    prompt: Optional[str] = Field(None, description="Direction for continuation")
    chapter_id: Optional[str] = Field(None)
    outline_node_id: Optional[str] = Field(None)
    model: Optional[str] = Field(None)
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    context_chapters: int = Field(5, ge=0, le=20)


class ConflictSuggestRequest(BaseModel):
    """Request for plot conflict suggestions."""
    prompt: Optional[str] = Field(None, max_length=500, description="Optional direction for conflict type")
    chapter_id: Optional[str] = Field(None, description="Target chapter for conflict analysis")
    outline_node_id: Optional[str] = Field(None)
    model: Optional[str] = Field(None)
    temperature: Optional[float] = Field(0.8, ge=0.0, le=2.0)


class ConflictAdoptRequest(BaseModel):
    """Request for adopting a plot conflict suggestion into the outline."""
    outline_node_id: str = Field(..., description="Parent outline node for the adopted conflict")
    type: Optional[str] = Field(None, max_length=50)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    suggested_outcome: Optional[str] = None
    involved_characters: list[str] = Field(default_factory=list)
    involved_character_ids: list[str] = Field(default_factory=list)


class CharacterChangesRequest(BaseModel):
    """Request for detecting character changes after a chapter."""
    model: Optional[str] = Field(None)
    temperature: Optional[float] = Field(0.3, ge=0.0, le=2.0)


class StoryAssistantRequest(BaseModel):
    """Request for the autonomous story assistant."""

    message: str = Field(..., min_length=1, description="User request or chat message")
    conversation_id: Optional[str] = Field(None, description="Persisted assistant conversation ID")
    edit_message_id: Optional[str] = Field(None, description="Existing user message ID to edit and resend")
    target_length: Optional[int] = Field(None, ge=1, description="Target length in Chinese characters for chapter drafting")
    chapter_id: Optional[str] = Field(None, description="Current chapter context")
    outline_node_id: Optional[str] = Field(None, description="Current outline node context")
    model: Optional[str] = Field(None, description="Model override")
    temperature: Optional[float] = Field(0.5, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    context_chapters: int = Field(8, ge=0, le=30)
    auto_create_chapter: bool = Field(True, description="Create a new chapter when the assistant decides it has a usable draft")
    history: list[dict] = Field(default_factory=list, description="Recent assistant conversation messages")


class AssistantConversationCreate(BaseModel):
    """Create a persisted assistant conversation."""

    title: Optional[str] = Field(None, max_length=200)
    chapter_id: Optional[str] = None
    outline_node_id: Optional[str] = None
    model: Optional[str] = None


class AssistantConversationUpdate(BaseModel):
    """Update assistant conversation metadata."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)


class AssistantMessageUpdate(BaseModel):
    """Edit a persisted user message."""

    content: str = Field(..., min_length=1)


class WorkspaceAssistantRequest(BaseModel):
    """Conversational assistant for project planning modules."""

    scope: Literal["outline", "characters", "worldbuilding", "project"] = Field(..., description="Management scope")
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    selected_outline_node_id: Optional[str] = None
    selected_character_id: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = Field(0.3, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    outline_batch_count: int = Field(3, ge=1, le=12, description="Preferred number of consecutive outline chapters to plan")
    auto_apply: bool = Field(True, description="Apply tool actions proposed by the model")
    history: list[dict] = Field(default_factory=list)
