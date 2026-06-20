"""REST API for API-free novel creation workflow."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.response import ApiResponse
from ..database.session import get_db
from ..services.workspace.tools.novel_creation import (
    apply_novel_blueprint,
    draft_novel_blueprint,
    review_novel_blueprint,
    start_novel_creation_session,
)

router = APIRouter(tags=["novel-creation"])


class NovelCreationStartRequest(BaseModel):
    mode: str = "template"
    user_brief: str = ""
    target_audience: str = ""
    genre: str = ""
    platform: str = ""


class NovelCreationDraftRequest(BaseModel):
    session_id: str
    execution_mode: Literal["template", "hybrid", "external_agent", "internal_llm"] = "hybrid"
    user_brief: str = ""
    feedback: str = ""
    revision_mode: Literal["initial", "refine", "regenerate"] = "initial"
    enhance_with_llm: bool = False
    skip_questions: bool = False
    answers: dict[str, str] | None = None


class NovelCreationReviewRequest(BaseModel):
    session_id: str
    execution_mode: Literal["template", "hybrid", "external_agent", "internal_llm"] = "hybrid"
    blueprint: Any | None = None


class NovelCreationApplyRequest(BaseModel):
    session_id: str
    blueprint_index: int = Field(0, ge=0)
    mode: Literal["manual", "auto"] = "auto"
    blueprint: Any | None = None


def _tool_response(result: dict[str, Any]) -> ApiResponse:
    status = result.get("status")
    detail = result.get("detail") or status or "success"
    if status not in ("ok", "need_clarification"):
        raise HTTPException(status_code=400, detail=detail)
    return ApiResponse.success(data=result.get("data"), message=detail)


@router.post("/novel-creation/start")
async def start_creation(payload: NovelCreationStartRequest, db: Session = Depends(get_db)):
    result = await start_novel_creation_session(db, "", payload.model_dump())
    return _tool_response(result)


@router.post("/novel-creation/draft")
async def draft_blueprints(payload: NovelCreationDraftRequest, db: Session = Depends(get_db)):
    result = await draft_novel_blueprint(db, "", payload.model_dump())
    return _tool_response(result)


@router.post("/novel-creation/review")
async def review_blueprint(payload: NovelCreationReviewRequest, db: Session = Depends(get_db)):
    result = await review_novel_blueprint(db, "", payload.model_dump())
    return _tool_response(result)


@router.post("/novel-creation/apply")
async def apply_blueprint(payload: NovelCreationApplyRequest, db: Session = Depends(get_db)):
    result = await apply_novel_blueprint(db, "", payload.model_dump())
    return _tool_response(result)


class RefreshQuestionRequest(BaseModel):
    session_id: str
    question: str
    existing_options: list[str] = []
    user_brief: str = ""


@router.post("/novel-creation/refresh-question")
async def refresh_question(payload: RefreshQuestionRequest, db: Session = Depends(get_db)):
    from app.services.workspace.tools.novel_creation import refresh_question_options
    result = await refresh_question_options(
        db=db,
        session_id=payload.session_id,
        question=payload.question,
        existing_options=payload.existing_options,
        user_brief=payload.user_brief,
    )
    return ApiResponse.success(data=result)
