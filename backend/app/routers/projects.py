"""Project (作品) CRUD API endpoints."""
import json
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database.session import get_db
from ..database.models import Project
from ..schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListItem
from ..core.response import ApiResponse
from ..core.exceptions import NotFoundError, ValidationError

router = APIRouter(tags=["projects"])


@router.get("/projects")
def list_projects(
    q: Optional[str] = Query(None, description="Search keyword for title or description"),
    db: Session = Depends(get_db)
):
    """Get project list with optional search."""
    query = db.query(Project)
    if q:
        keyword = f"%{q}%"
        query = query.filter(
            or_(
                Project.title.like(keyword),
                Project.description.like(keyword),
            )
        )
    projects = query.order_by(Project.updated_at.desc()).all()
    items = [ProjectListItem.model_validate(p) for p in projects]
    return ApiResponse.success(data={"items": [item.model_dump() for item in items], "total": len(items)})


@router.post("/projects")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project."""
    data = payload.model_dump()
    if data.get("tags") is not None:
        data["tags"] = json.dumps(data["tags"], ensure_ascii=False)

    project = Project(**data)
    db.add(project)
    db.commit()
    db.refresh(project)
    return ApiResponse.success(data=ProjectResponse.model_validate(project).model_dump(), message="作品创建成功")


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get project details by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundError("作品不存在")
    return ApiResponse.success(data=ProjectResponse.model_validate(project).model_dump())


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)):
    """Update project information."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundError("作品不存在")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise ValidationError("未提供任何更新字段")

    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = json.dumps(update_data["tags"], ensure_ascii=False)

    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return ApiResponse.success(data=ProjectResponse.model_validate(project).model_dump(), message="作品更新成功")


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a project and all associated data (cascaded by ORM)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundError("作品不存在")

    db.delete(project)
    db.commit()
    return ApiResponse.success(message="作品已删除")
