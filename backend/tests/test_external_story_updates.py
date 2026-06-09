"""Tests for external story update application tool."""
import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.workspace.registry import registry


class ExternalStoryUpdatesToolRegisteredTest(unittest.TestCase):
    """Verify apply_external_story_updates is registered."""

    def test_registered(self):
        td = registry.get("apply_external_story_updates")
        self.assertIsNotNone(td)
        self.assertEqual(td.tool_type, "write")
        self.assertTrue(td.writes_project_data)

    def test_in_project_writing_pack(self):
        from app.mcp.adapter import list_mcp_tools
        tools = list_mcp_tools(permission_pack="project_writing")
        names = {t.name for t in tools}
        self.assertIn("apply_external_story_updates", names)


class ApplyExternalStoryUpdatesTest(unittest.TestCase):
    """Verify apply_external_story_updates behavior."""

    def test_invalid_updates_skipped(self):
        from app.services.workspace.tools.external_story_updates import apply_external_story_updates
        db = MagicMock()
        result = asyncio.run(apply_external_story_updates(db, "p1", {"updates": "invalid"}))
        self.assertEqual(result["status"], "skipped")

    def test_manual_mode_returns_candidates(self):
        from app.services.workspace.tools.external_story_updates import apply_external_story_updates
        char = MagicMock()
        char.id = "c1"
        char.name = "Hero"

        db = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.first.return_value = char
        db.query.return_value = query_mock

        result = asyncio.run(apply_external_story_updates(db, "p1", {
            "chapter_id": "ch1",
            "updates": {
                "characters": [
                    {"id": "c1", "current_location": "Castle", "current_goal": "Save world"},
                ],
            },
            "mode": "manual",
        }))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["mode"], "manual")
        self.assertGreater(len(result["data"]["candidates"]), 0)

    def test_auto_mode_applies_updates(self):
        from app.services.workspace.tools.external_story_updates import apply_external_story_updates
        char = MagicMock()
        char.id = "c1"
        char.name = "Hero"

        db = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.first.return_value = char
        db.query.return_value = query_mock

        result = asyncio.run(apply_external_story_updates(db, "p1", {
            "chapter_id": "ch1",
            "updates": {
                "characters": [
                    {"id": "c1", "current_location": "Castle"},
                ],
            },
            "mode": "auto",
        }))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["mode"], "auto")
        self.assertGreater(len(result["data"]["applied"]), 0)

    def test_missing_character_skipped(self):
        from app.services.workspace.tools.external_story_updates import apply_external_story_updates
        db = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.first.return_value = None
        db.query.return_value = query_mock

        result = asyncio.run(apply_external_story_updates(db, "p1", {
            "updates": {
                "characters": [{"id": "nonexistent"}],
            },
        }))
        self.assertEqual(result["status"], "ok")
        self.assertGreater(len(result["data"]["skipped"]), 0)


if __name__ == "__main__":
    unittest.main()
