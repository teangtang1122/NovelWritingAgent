"""API router for external Agent runs."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.response import ApiResponse
from ..core.db_helpers import get_project_or_404
from ..database.session import get_db
from ..database.models import AgentRun, AgentRunEvent
from ..schemas.agent_run import (
    AgentRunCreate,
    AgentRunRead,
    AgentRunEventCreate,
    AgentRunEventRead,
    AgentRunListResponse,
    AgentRunEventListResponse,
)
from ..services.external_agent.run_service import (
    create_run,
    get_run,
    list_runs,
    add_event,
    get_events,
    cancel_run,
    update_run_status,
)

router = APIRouter(prefix="/projects/{project_id}/agent-runs", tags=["external-agent"])


def _run_to_read(run: AgentRun) -> AgentRunRead:
    return AgentRunRead(
        id=run.id,
        project_id=run.project_id,
        source=run.source,
        client_name=run.client_name,
        title=run.title,
        status=run.status,
        current_step=run.current_step,
        summary=run.summary,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


def _event_to_read(event: AgentRunEvent) -> AgentRunEventRead:
    return AgentRunEventRead(
        id=event.id,
        run_id=event.run_id,
        sequence=event.sequence,
        event_type=event.event_type,
        status=event.status,
        message=event.message,
        payload_json=event.payload_json,
        created_at=event.created_at,
    )


@router.post("")
def create_agent_run(
    project_id: str,
    body: AgentRunCreate,
    db: Session = Depends(get_db),
):
    """Create a new Agent run."""
    get_project_or_404(db, project_id)
    run = create_run(
        db, project_id,
        source=body.source,
        client_name=body.client_name,
        title=body.title,
    )
    return ApiResponse.success(data=_run_to_read(run).model_dump(), message="Run created")


@router.get("")
def list_agent_runs(
    project_id: str,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """List Agent runs for a project."""
    get_project_or_404(db, project_id)
    runs = list_runs(db, project_id, status=status)
    return ApiResponse.success(data={
        "items": [_run_to_read(r).model_dump() for r in runs],
        "total": len(runs),
    })


@router.get("/{run_id}")
def get_agent_run(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
):
    """Get a single Agent run."""
    get_project_or_404(db, project_id)
    run = get_run(db, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return ApiResponse.success(data=_run_to_read(run).model_dump())


@router.get("/{run_id}/events")
def get_agent_run_events(
    project_id: str,
    run_id: str,
    after_sequence: int = 0,
    db: Session = Depends(get_db),
):
    """Get events for an Agent run."""
    get_project_or_404(db, project_id)
    run = get_run(db, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    events = get_events(db, run_id, after_sequence=after_sequence)
    return ApiResponse.success(data={
        "items": [_event_to_read(e).model_dump() for e in events],
        "total": len(events),
    })


@router.post("/{run_id}/events")
def add_agent_run_event(
    project_id: str,
    run_id: str,
    body: AgentRunEventCreate,
    db: Session = Depends(get_db),
):
    """Add an event to an Agent run."""
    get_project_or_404(db, project_id)
    run = get_run(db, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    event = add_event(
        db, run_id, body.event_type,
        status=body.status,
        message=body.message,
        payload_json=body.payload_json,
    )
    if not event:
        raise HTTPException(status_code=400, detail="Cannot add event to terminal run")
    return ApiResponse.success(data=_event_to_read(event).model_dump(), message="Event added")


@router.get("/{run_id}/stream")
async def stream_agent_run_events(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
):
    """SSE stream for Agent run events."""
    get_project_or_404(db, project_id)
    run = get_run(db, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        # Send existing events first
        last_seq = 0
        events = get_events(db, run_id)
        for event in events:
            payload = _event_to_read(event).model_dump()
            # Convert datetime to string for JSON
            for k, v in payload.items():
                if hasattr(v, 'isoformat'):
                    payload[k] = v.isoformat()
            yield f"event: agent_run_event\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            last_seq = event.sequence

        # Poll for new events
        while True:
            await asyncio.sleep(1)
            # Re-query run status
            db.refresh(run)
            new_events = get_events(db, run_id, after_sequence=last_seq)
            for event in new_events:
                payload = _event_to_read(event).model_dump()
                for k, v in payload.items():
                    if hasattr(v, 'isoformat'):
                        payload[k] = v.isoformat()
                yield f"event: agent_run_event\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_seq = event.sequence

            # Stop if run is terminal
            if run.status in ("completed", "failed", "cancelled"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{run_id}/cancel")
def cancel_agent_run(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
):
    """Cancel an Agent run."""
    get_project_or_404(db, project_id)
    run = get_run(db, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    cancelled = cancel_run(db, run_id)
    return ApiResponse.success(data=_run_to_read(cancelled).model_dump(), message="Run cancelled")
