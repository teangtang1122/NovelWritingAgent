"""Tests for MCP server config model and schema."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database.models import McpServerConfig
from app.schemas.mcp import (
    McpServerConfigCreate,
    McpServerConfigUpdate,
    McpServerConfigRead,
)


class McpServerConfigModelTest(unittest.TestCase):
    """Verify the McpServerConfig model has required fields."""

    def test_has_table_name(self):
        self.assertEqual(McpServerConfig.__tablename__, "mcp_server_configs")

    def test_has_required_columns(self):
        columns = {c.name for c in McpServerConfig.__table__.columns}
        required = {
            "id", "project_id", "name", "transport", "command", "url",
            "enabled", "status", "last_error", "created_at", "updated_at",
        }
        missing = required - columns
        self.assertEqual(missing, set(), f"Missing columns: {missing}")

    def test_default_transport(self):
        col = McpServerConfig.__table__.columns["transport"]
        self.assertEqual(col.default.arg, "stdio")

    def test_default_enabled(self):
        col = McpServerConfig.__table__.columns["enabled"]
        self.assertTrue(col.default.arg)

    def test_default_status(self):
        col = McpServerConfig.__table__.columns["status"]
        self.assertEqual(col.default.arg, "disconnected")


class McpServerConfigSchemaTest(unittest.TestCase):
    """Verify Pydantic schemas for MCP server config."""

    def test_create_schema(self):
        data = McpServerConfigCreate(name="test-server", transport="stdio", command="python mcp.py")
        self.assertEqual(data.name, "test-server")
        self.assertEqual(data.transport, "stdio")
        self.assertTrue(data.enabled)

    def test_create_schema_defaults(self):
        data = McpServerConfigCreate(name="test")
        self.assertEqual(data.transport, "stdio")
        self.assertIsNone(data.command)
        self.assertIsNone(data.url)
        self.assertTrue(data.enabled)

    def test_update_schema_partial(self):
        data = McpServerConfigUpdate(enabled=False)
        self.assertFalse(data.enabled)
        self.assertIsNone(data.name)

    def test_read_schema_from_dict(self):
        data = McpServerConfigRead(
            id="abc",
            project_id="p1",
            name="test",
            transport="stdio",
            command="python mcp.py",
            url=None,
            enabled=True,
            status="disconnected",
            last_error=None,
            created_at="2026-06-07T00:00:00",
            updated_at=None,
        )
        self.assertEqual(data.id, "abc")
        self.assertEqual(data.status, "disconnected")


if __name__ == "__main__":
    unittest.main()
