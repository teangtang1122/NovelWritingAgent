"""API router for scheduled tasks."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.response import ApiResponse
from ..core.db_helpers import get_project_or_404
from ..database.session import get_db
from ..database.models import ScheduledTask
from ..schemas.scheduler import (
    ScheduledTaskCreate,
    ScheduledTaskListResponse,
    ScheduledTaskResponse,
    ScheduledTaskRunResponse,
    ScheduledTaskUpdate,
)
from ..services.scheduler.engine import _compute_next_run, _execute_task, get_active_tasks

router = APIRouter(prefix="/projects/{project_id}/scheduled-tasks", tags=["scheduler"])


def _task_to_response(task: ScheduledTask) -> ScheduledTaskResponse:
    return ScheduledTaskResponse(
        id=task.id,
        project_id=task.project_id,
        name=task.name,
        prompt=task.prompt,
        cron_expr=task.cron_expr,
        interval_minutes=task.interval_minutes,
        tool_policy=task.tool_policy or [],
        status=task.status,
        last_run_at=task.last_run_at,
        last_run_status=task.last_run_status,
        last_run_output=task.last_run_output,
        next_run_at=task.next_run_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("")
def list_scheduled_tasks(
    project_id: str,
    db: Session = Depends(get_db),
):
    """List all scheduled tasks for a project."""
    get_project_or_404(db, project_id)
    tasks = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.project_id == project_id)
        .order_by(ScheduledTask.created_at.desc())
        .all()
    )
    payload = ScheduledTaskListResponse(
        items=[_task_to_response(t) for t in tasks],
        total=len(tasks),
    )
    return ApiResponse.success(data=payload)


@router.post("")
def create_scheduled_task(
    project_id: str,
    body: ScheduledTaskCreate,
    db: Session = Depends(get_db),
):
    """Create a new scheduled task."""
    get_project_or_404(db, project_id)

    # Validate cron expression if provided
    if body.cron_expr:
        try:
            from croniter import croniter
            croniter(body.cron_expr)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {exc}")

    task = ScheduledTask(
        project_id=project_id,
        name=body.name,
        prompt=body.prompt,
        cron_expr=body.cron_expr,
        interval_minutes=body.interval_minutes,
        tool_policy=body.tool_policy,
        status="active",
    )
    db.add(task)
    db.flush()

    # Compute initial next_run_at
    task.next_run_at = _compute_next_run(task)
    db.commit()
    db.refresh(task)

    return ApiResponse.success(data=_task_to_response(task), message="定时任务已创建")


@router.get("/{task_id}")
def get_scheduled_task(
    project_id: str,
    task_id: str,
    db: Session = Depends(get_db),
):
    """Get a scheduled task by ID."""
    get_project_or_404(db, project_id)
    task = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.id == task_id, ScheduledTask.project_id == project_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return ApiResponse.success(data=_task_to_response(task))


@router.put("/{task_id}")
def update_scheduled_task(
    project_id: str,
    task_id: str,
    body: ScheduledTaskUpdate,
    db: Session = Depends(get_db),
):
    """Update a scheduled task."""
    get_project_or_404(db, project_id)
    task = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.id == task_id, ScheduledTask.project_id == project_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if body.name is not None:
        task.name = body.name
    if body.prompt is not None:
        task.prompt = body.prompt
    if body.cron_expr is not None:
        # Validate cron expression
        if body.cron_expr:
            try:
                from croniter import croniter
                croniter(body.cron_expr)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Invalid cron expression: {exc}")
        task.cron_expr = body.cron_expr
    if body.interval_minutes is not None:
        task.interval_minutes = body.interval_minutes
    if body.tool_policy is not None:
        task.tool_policy = body.tool_policy
    if body.status is not None:
        if body.status not in ("active", "paused"):
            raise HTTPException(status_code=400, detail="Status must be 'active' or 'paused'")
        task.status = body.status

    # Recompute next_run_at
    task.next_run_at = _compute_next_run(task)
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    return ApiResponse.success(data=_task_to_response(task), message="定时任务已更新")


@router.delete("/{task_id}")
def delete_scheduled_task(
    project_id: str,
    task_id: str,
    db: Session = Depends(get_db),
):
    """Delete a scheduled task."""
    get_project_or_404(db, project_id)
    task = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.id == task_id, ScheduledTask.project_id == project_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()

    return ApiResponse.success(data={"status": "ok", "detail": "Task deleted"}, message="定时任务已删除")


@router.post("/{task_id}/run-now")
def run_scheduled_task_now(
    project_id: str,
    task_id: str,
    db: Session = Depends(get_db),
):
    """Run a scheduled task immediately."""
    get_project_or_404(db, project_id)
    task = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.id == task_id, ScheduledTask.project_id == project_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check if task is already running
    active = get_active_tasks()
    if task_id in active:
        raise HTTPException(status_code=409, detail="Task is already running")

    # Run task synchronously (blocking)
    started_at = datetime.utcnow()
    try:
        _execute_task(task_id)
        db.refresh(task)
        payload = ScheduledTaskRunResponse(
            task_id=task_id,
            status=task.last_run_status or "completed",
            output=task.last_run_output,
            started_at=started_at,
            completed_at=datetime.utcnow(),
        )
        return ApiResponse.success(data=payload, message="定时任务执行完成")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Task execution failed: {exc}")


@router.get("/{task_id}/logs")
def get_scheduled_task_logs(
    project_id: str,
    task_id: str,
    db: Session = Depends(get_db),
):
    """Get the last run output for a scheduled task."""
    get_project_or_404(db, project_id)
    task = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.id == task_id, ScheduledTask.project_id == project_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return ApiResponse.success(data={
        "task_id": task_id,
        "last_run_at": task.last_run_at,
        "last_run_status": task.last_run_status,
        "last_run_output": task.last_run_output,
    })
