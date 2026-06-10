"""Tests for MCP error visibility improvements (EAC-0403)."""
import asyncio
import json
import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class McpErrorContractTest(unittest.TestCase):
    """Verify MCP error responses include actionable details."""

    def test_error_includes_tool_name(self):
        """Error payload must include the tool name."""
        from app.mcp.adapter import _build_error_payload

        exc = ValueError("something broke")
        payload = _build_error_payload(tool_name="create_chapter", exc=exc)

        self.assertEqual(payload["tool"], "create_chapter")
        self.assertEqual(payload["status"], "error")

    def test_error_includes_error_type(self):
        """Error payload must include error_type."""
        from app.mcp.adapter import _build_error_payload

        exc = RuntimeError("oops")
        payload = _build_error_payload(tool_name="test_tool", exc=exc)

        self.assertEqual(payload["error_type"], "RuntimeError")

    def test_error_includes_traceback_code(self):
        """Error payload must include a short traceback_code for log correlation."""
        from app.mcp.adapter import _build_error_payload

        exc = ValueError("test")
        payload = _build_error_payload(tool_name="test_tool", exc=exc)

        self.assertIn("traceback_code", payload)
        # Should be a short hex string
        self.assertEqual(len(payload["traceback_code"]), 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in payload["traceback_code"]))

    def test_pending_rollback_error_not_hidden(self):
        """PendingRollbackError must not be hidden behind generic message."""
        from app.mcp.adapter import _build_error_payload

        try:
            from sqlalchemy.exc import PendingRollbackError
            # Create a real PendingRollbackError
            exc = PendingRollbackError("previous statement failed", None)
        except ImportError:
            # If SQLAlchemy not available, simulate
            class PendingRollbackError(Exception):
                pass
            exc = PendingRollbackError("previous statement failed")

        payload = _build_error_payload(tool_name="save_external_cataloging_facts", exc=exc)

        self.assertEqual(payload["error_type"], "PendingRollbackError")
        self.assertNotIn("Tool execution failed", payload["detail"])
        self.assertIn("rolled back", payload["detail"].lower())
        self.assertIn("next_suggestions", payload)
        self.assertTrue(len(payload["next_suggestions"]) > 0)

    def test_pending_rollback_suggests_retry(self):
        """PendingRollbackError should suggest retrying."""
        from app.mcp.adapter import _build_error_payload

        try:
            from sqlalchemy.exc import PendingRollbackError
            exc = PendingRollbackError("test", None)
        except ImportError:
            class PendingRollbackError(Exception):
                pass
            exc = PendingRollbackError("test")

        payload = _build_error_payload(tool_name="test", exc=exc)
        suggestions = payload.get("next_suggestions", [])
        self.assertTrue(any("retry" in s.lower() for s in suggestions))

    def test_integrity_error_suggestion(self):
        """IntegrityError should suggest checking duplicates."""
        from app.mcp.adapter import _build_error_payload

        class IntegrityError(Exception):
            pass

        exc = IntegrityError("UNIQUE constraint failed")
        payload = _build_error_payload(tool_name="create_character", exc=exc)

        self.assertEqual(payload["error_type"], "IntegrityError")
        self.assertIn("next_suggestions", payload)

    def test_custom_detail_preserved(self):
        """Custom detail override is used when provided."""
        from app.mcp.adapter import _build_error_payload

        exc = ValueError("raw message")
        payload = _build_error_payload(
            tool_name="test", exc=exc, detail="User-friendly message",
        )

        self.assertEqual(payload["detail"], "User-friendly message")

    def test_error_payload_is_valid_json(self):
        """Error payload must serialize to valid JSON."""
        from app.mcp.adapter import _build_error_payload

        exc = Exception("test")
        payload = _build_error_payload(tool_name="test_tool", exc=exc)

        # Should not raise
        serialized = json.dumps(payload, ensure_ascii=False)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["status"], "error")


class McpErrorIntegrationTest(unittest.TestCase):
    """Verify execute_tool returns enhanced error format."""

    def test_execute_tool_exception_includes_error_fields(self):
        """When execute_workspace_action raises, result includes error_type and traceback_code."""
        from app.mcp.adapter import execute_tool
        from app.services.workspace.registry import registry

        # Use a real read-only tool that exists in the registry
        # list_chapters is read-only, no confirmation needed
        self.assertIsNotNone(registry.get("list_chapters"))

        # Monkeypatch the handler to raise
        original_handler = registry.get_handler("list_chapters")

        async def failing_handler(db, project_id, args):
            raise RuntimeError("connection lost")

        td = registry.get("list_chapters")
        object.__setattr__(td, "handler", failing_handler)
        try:
            db = MagicMock()
            result = _run(execute_tool(
                db, "proj-1", "list_chapters", {},
                permission_pack="readonly_collaboration",
            ))

            self.assertTrue(result.is_error)
            text = result.content[0]["text"]
            payload = json.loads(text)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error_type"], "RuntimeError")
            self.assertIn("traceback_code", payload)
            self.assertEqual(payload["tool"], "list_chapters")
        finally:
            # Restore original handler
            object.__setattr__(td, "handler", original_handler)


if __name__ == "__main__":
    unittest.main()
