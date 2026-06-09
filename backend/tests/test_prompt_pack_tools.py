"""Tests for prompt pack tools — list, get, playbook, rubric."""
import asyncio
import json
import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.workspace.registry import registry


class PromptPackToolsRegisteredTest(unittest.TestCase):
    """Verify prompt pack tools are registered in the workspace registry."""

    def test_list_prompt_packs_registered(self):
        td = registry.get("list_prompt_packs")
        self.assertIsNotNone(td)
        self.assertEqual(td.tool_type, "read")

    def test_get_prompt_pack_registered(self):
        td = registry.get("get_prompt_pack")
        self.assertIsNotNone(td)

    def test_get_tool_playbook_registered(self):
        td = registry.get("get_tool_playbook")
        self.assertIsNotNone(td)

    def test_get_quality_rubric_registered(self):
        td = registry.get("get_quality_rubric")
        self.assertIsNotNone(td)

    def test_all_prompt_tools_are_readonly(self):
        from app.mcp.permissions import get_tier
        for name in ["list_prompt_packs", "get_prompt_pack", "get_tool_playbook", "get_quality_rubric"]:
            td = registry.get(name)
            self.assertIsNotNone(td)
            self.assertEqual(get_tier(td), "readonly", f"{name} should be readonly")


class ListPromptPacksTest(unittest.TestCase):
    """Verify list_prompt_packs tool behavior."""

    def test_returns_packs(self):
        from app.services.workspace.tools.prompt_packs import list_prompt_packs
        db = MagicMock()
        # Mock query chain
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = []
        db.query.return_value = query_mock

        result = asyncio.run(list_prompt_packs(db, "p1", {}))
        self.assertEqual(result["status"], "ok")
        self.assertIn("items", result["data"])


class GetPromptPackTest(unittest.TestCase):
    """Verify get_prompt_pack tool behavior."""

    def test_missing_pack_returns_skipped(self):
        from app.services.workspace.tools.prompt_packs import get_prompt_pack
        db = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.first.return_value = None
        db.query.return_value = query_mock

        result = asyncio.run(get_prompt_pack(db, "p1", {"scope": "nonexistent"}))
        self.assertEqual(result["status"], "skipped")


class ToolRegistrationTest(unittest.TestCase):
    """Verify prompt pack tools appear in MCP tool list."""

    def test_tools_in_readonly_pack(self):
        from app.mcp.adapter import list_mcp_tools
        tools = list_mcp_tools(permission_pack="readonly_collaboration")
        names = {t.name for t in tools}
        self.assertIn("list_prompt_packs", names)
        self.assertIn("get_prompt_pack", names)
        self.assertIn("get_tool_playbook", names)
        self.assertIn("get_quality_rubric", names)


if __name__ == "__main__":
    unittest.main()
