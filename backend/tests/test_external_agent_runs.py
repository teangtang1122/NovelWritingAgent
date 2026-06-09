"""Tests for external Agent run persistence model and schema."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database.models import AgentRun, AgentRunEvent
from app.schemas.agent_run import (
    AgentRunCreate,
    AgentRunRead,
    AgentRunEventCreate,
    AgentRunEventRead,
    AgentRunListResponse,
    AgentRunEventListResponse,
)


class AgentRunModelTest(unittest.TestCase):
    """Verify the AgentRun model has required fields."""

    def test_has_table_name(self):
        self.assertEqual(AgentRun.__tablename__, "agent_runs")

    def test_has_required_columns(self):
        columns = {c.name for c in AgentRun.__table__.columns}
        required = {
            "id", "project_id", "source", "client_name", "title",
            "status", "current_step", "summary",
            "created_at", "updated_at", "completed_at",
        }
        missing = required - columns
        self.assertEqual(missing, set(), f"Missing columns: {missing}")

    def test_default_status(self):
        col = AgentRun.__table__.columns["status"]
        self.assertEqual(col.default.arg, "created")

    def test_default_source(self):
        col = AgentRun.__table__.columns["source"]
        self.assertEqual(col.default.arg, "mcp")


class AgentRunEventModelTest(unittest.TestCase):
    """Verify the AgentRunEvent model has required fields."""

    def test_has_table_name(self):
        self.assertEqual(AgentRunEvent.__tablename__, "agent_run_events")

    def test_has_required_columns(self):
        columns = {c.name for c in AgentRunEvent.__table__.columns}
        required = {
            "id", "run_id", "sequence", "event_type",
            "status", "message", "payload_json", "created_at",
        }
        missing = required - columns
        self.assertEqual(missing, set(), f"Missing columns: {missing}")

    def test_default_status(self):
        col = AgentRunEvent.__table__.columns["status"]
        self.assertEqual(col.default.arg, "ok")


class AgentRunSchemaTest(unittest.TestCase):
    """Verify Pydantic schemas for Agent runs."""

    def test_create_schema(self):
        data = AgentRunCreate(source="mcp", client_name="claude-code")
        self.assertEqual(data.source, "mcp")
        self.assertEqual(data.client_name, "claude-code")

    def test_create_schema_defaults(self):
        data = AgentRunCreate()
        self.assertEqual(data.source, "mcp")
        self.assertIsNone(data.client_name)

    def test_read_schema_from_dict(self):
        from datetime import datetime
        data = AgentRunRead(
            id="r1", project_id="p1", source="mcp",
            client_name="codex", title="Test Run",
            status="running", current_step="Planning",
            summary=None, created_at=datetime(2026, 6, 9),
        )
        self.assertEqual(data.id, "r1")
        self.assertEqual(data.status, "running")


class AgentRunEventSchemaTest(unittest.TestCase):
    """Verify Pydantic schemas for Agent run events."""

    def test_create_schema(self):
        data = AgentRunEventCreate(
            event_type="progress",
            status="ok",
            message="Reading chapters",
        )
        self.assertEqual(data.event_type, "progress")

    def test_read_schema_from_dict(self):
        from datetime import datetime
        data = AgentRunEventRead(
            id="e1", run_id="r1", sequence=1,
            event_type="plan", status="ok",
            message=None, payload_json='{"steps":["step1"]}',
            created_at=datetime(2026, 6, 9),
        )
        self.assertEqual(data.sequence, 1)


class AgentRunListResponseTest(unittest.TestCase):
    """Verify list response schemas."""

    def test_run_list_response(self):
        resp = AgentRunListResponse(items=[], total=0)
        self.assertEqual(resp.total, 0)

    def test_event_list_response(self):
        resp = AgentRunEventListResponse(items=[], total=0)
        self.assertEqual(resp.total, 0)


if __name__ == "__main__":
    unittest.main()
