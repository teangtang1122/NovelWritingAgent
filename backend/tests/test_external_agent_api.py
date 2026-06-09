"""Tests for external Agent run API router."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.external_agent import router, _run_to_read, _event_to_read
from app.database.models import AgentRun, AgentRunEvent
from app.schemas.agent_run import AgentRunRead, AgentRunEventRead


class RunToReadTest(unittest.TestCase):
    """Verify _run_to_read conversion."""

    def test_converts_model_to_schema(self):
        from datetime import datetime
        run = AgentRun()
        run.id = "r1"
        run.project_id = "p1"
        run.source = "mcp"
        run.client_name = "claude-code"
        run.title = "Test Run"
        run.status = "running"
        run.current_step = "Planning"
        run.summary = None
        run.created_at = datetime(2026, 6, 9)
        run.updated_at = None
        run.completed_at = None

        result = _run_to_read(run)
        self.assertIsInstance(result, AgentRunRead)
        self.assertEqual(result.id, "r1")
        self.assertEqual(result.status, "running")


class EventToReadTest(unittest.TestCase):
    """Verify _event_to_read conversion."""

    def test_converts_model_to_schema(self):
        from datetime import datetime
        event = AgentRunEvent()
        event.id = "e1"
        event.run_id = "r1"
        event.sequence = 1
        event.event_type = "progress"
        event.status = "ok"
        event.message = "Reading"
        event.payload_json = None
        event.created_at = datetime(2026, 6, 9)

        result = _event_to_read(event)
        self.assertIsInstance(result, AgentRunEventRead)
        self.assertEqual(result.sequence, 1)


class RouterTest(unittest.TestCase):
    """Verify router configuration."""

    def test_router_has_prefix(self):
        self.assertIn("agent-runs", router.prefix)

    def test_router_has_routes(self):
        routes = [r.path for r in router.routes]
        self.assertGreater(len(routes), 0)

    def test_router_has_create_endpoint(self):
        has_post = False
        for r in router.routes:
            if hasattr(r, 'methods') and "POST" in r.methods:
                has_post = True
                break
        self.assertTrue(has_post, "No POST endpoint found")

    def test_router_has_stream_endpoint(self):
        paths = [r.path for r in router.routes]
        self.assertTrue(any("stream" in p for p in paths))


if __name__ == "__main__":
    unittest.main()
