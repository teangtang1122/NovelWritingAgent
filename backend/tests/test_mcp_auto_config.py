"""Tests for automatic MCP client configuration for local CLI providers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.external_agent import mcp_auto_config


class McpAutoConfigTest(unittest.TestCase):
    def test_codex_config_replaces_only_moshu_block(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_path = config_dir / "config.toml"
            config_path.write_text(
                "\n".join([
                    '[profiles.default]',
                    'model = "gpt-5"',
                    "",
                    "[mcp_servers.other]",
                    'type = "stdio"',
                    'command = "other"',
                    "",
                    "[mcp_servers.moshu]",
                    'type = "stdio"',
                    'command = "old"',
                    'args = ["old"]',
                    "",
                    "[ui]",
                    'theme = "dark"',
                    "",
                ]),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"CODEX_HOME": str(config_dir), "MOSHU_DISABLE_AUTO_MCP_SETUP": ""}):
                with patch("app.services.external_agent.mcp_auto_config.shutil.which", return_value=None):
                    result = mcp_auto_config.auto_configure_mcp_for_provider("codex_cli")

            self.assertEqual(result["status"], "configured")
            new_text = config_path.read_text(encoding="utf-8")
            self.assertIn("[mcp_servers.other]", new_text)
            self.assertIn("[ui]", new_text)
            self.assertIn("[mcp_servers.moshu]", new_text)
            self.assertIn("--permission-pack", new_text)
            self.assertIn('"auto"', new_text)
            self.assertNotIn('command = "old"', new_text)
            self.assertTrue(list(config_dir.glob("config.toml.bak-*")))

    def test_claude_config_uses_remove_then_add(self):
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ""

        with patch.dict(os.environ, {"MOSHU_DISABLE_AUTO_MCP_SETUP": ""}):
            with patch("app.services.external_agent.mcp_auto_config._resolve_command", return_value="claude"):
                with patch("app.services.external_agent.mcp_auto_config.subprocess.run", return_value=completed) as run:
                    result = mcp_auto_config.auto_configure_mcp_for_provider("claude_cli", cli_command="claude")

        self.assertEqual(result["status"], "configured")
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(calls[0][:5], ["claude", "mcp", "remove", "-s", "user"])
        self.assertEqual(calls[1][:7], ["claude", "mcp", "add", "-s", "user", "moshu", "--"])
        self.assertIn("--permission-pack", calls[1])
        self.assertIn("auto", calls[1])

    def test_disabled_by_env(self):
        with patch.dict(os.environ, {"MOSHU_DISABLE_AUTO_MCP_SETUP": "1"}):
            result = mcp_auto_config.auto_configure_mcp_for_provider("claude_cli", cli_command="claude")
        self.assertEqual(result["status"], "skipped")
        self.assertFalse(result["enabled"])


if __name__ == "__main__":
    unittest.main()
