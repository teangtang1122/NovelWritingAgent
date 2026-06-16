"""Tests for automatic MCP client configuration for local CLI providers."""

from __future__ import annotations

import json
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

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / ".claude" / "settings.json"
            with patch.dict(os.environ, {"MOSHU_DISABLE_AUTO_MCP_SETUP": ""}):
                with patch("app.services.external_agent.mcp_auto_config._resolve_command", return_value="claude"):
                    with patch("app.services.external_agent.mcp_auto_config.subprocess.run", return_value=completed) as run:
                        with patch("app.services.external_agent.mcp_auto_config._claude_settings_path", return_value=settings_path):
                            result = mcp_auto_config.auto_configure_mcp_for_provider("claude_cli", cli_command="claude")

            self.assertEqual(result["status"], "configured")
            calls = [call.args[0] for call in run.call_args_list]
            self.assertEqual(calls[0][:5], ["claude", "mcp", "remove", "-s", "user"])
            self.assertEqual(calls[1][:7], ["claude", "mcp", "add", "-s", "user", "moshu", "--"])
            self.assertIn("--permission-pack", calls[1])
            self.assertIn("auto", calls[1])
            # Verify permission was auto-added
            self.assertTrue(settings_path.exists())
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertIn("mcp__moshu__*", settings.get("permissions", {}).get("allow", []))

    def test_claude_config_permission_added_to_existing_settings(self):
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ""

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps({
                    "theme": "dark",
                    "permissions": {"allow": ["Bash(git *)"]},
                }),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"MOSHU_DISABLE_AUTO_MCP_SETUP": ""}):
                with patch("app.services.external_agent.mcp_auto_config._resolve_command", return_value="claude"):
                    with patch("app.services.external_agent.mcp_auto_config.subprocess.run", return_value=completed):
                        with patch("app.services.external_agent.mcp_auto_config._claude_settings_path", return_value=settings_path):
                            result = mcp_auto_config.auto_configure_mcp_for_provider("claude_cli", cli_command="claude")

            self.assertEqual(result["status"], "configured")
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            allow = settings["permissions"]["allow"]
            # Existing entries preserved
            self.assertIn("Bash(git *)", allow)
            # Moshu wildcard added
            self.assertIn("mcp__moshu__*", allow)
            # Other settings preserved
            self.assertEqual(settings["theme"], "dark")

    def test_claude_config_permission_already_present_no_duplicate(self):
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ""

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps({
                    "permissions": {"allow": ["mcp__moshu__*", "Bash(git *)"]},
                }),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"MOSHU_DISABLE_AUTO_MCP_SETUP": ""}):
                with patch("app.services.external_agent.mcp_auto_config._resolve_command", return_value="claude"):
                    with patch("app.services.external_agent.mcp_auto_config.subprocess.run", return_value=completed):
                        with patch("app.services.external_agent.mcp_auto_config._claude_settings_path", return_value=settings_path):
                            mcp_auto_config.auto_configure_mcp_for_provider("claude_cli", cli_command="claude")

            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            allow = settings["permissions"]["allow"]
            # No duplicate added
            self.assertEqual(allow.count("mcp__moshu__*"), 1)

    def test_disabled_by_env(self):
        with patch.dict(os.environ, {"MOSHU_DISABLE_AUTO_MCP_SETUP": "1"}):
            result = mcp_auto_config.auto_configure_mcp_for_provider("claude_cli", cli_command="claude")
        self.assertEqual(result["status"], "skipped")
        self.assertFalse(result["enabled"])

    def test_opencode_config_creates_new_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_path = config_dir / "config.json"

            with patch.dict(os.environ, {"OPENCODE_HOME": str(config_dir), "MOSHU_DISABLE_AUTO_MCP_SETUP": ""}):
                with patch("app.services.external_agent.mcp_auto_config.shutil.which", return_value=None):
                    result = mcp_auto_config.auto_configure_mcp_for_provider("opencode_cli")

            self.assertEqual(result["status"], "configured")
            self.assertTrue(config_path.exists())
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIn("moshu", config["mcpServers"])
            self.assertIn("--permission-pack", config["mcpServers"]["moshu"]["args"])

    def test_opencode_config_preserves_existing_servers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_path = config_dir / "config.json"
            config_path.write_text(
                json.dumps({
                    "mcpServers": {
                        "other-server": {
                            "command": "other",
                            "args": ["--flag"],
                        }
                    },
                    "theme": "dark",
                }),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"OPENCODE_HOME": str(config_dir), "MOSHU_DISABLE_AUTO_MCP_SETUP": ""}):
                with patch("app.services.external_agent.mcp_auto_config.shutil.which", return_value=None):
                    result = mcp_auto_config.auto_configure_mcp_for_provider("opencode_cli")

            self.assertEqual(result["status"], "configured")
            config = json.loads(config_path.read_text(encoding="utf-8"))
            # Existing server preserved
            self.assertIn("other-server", config["mcpServers"])
            self.assertEqual(config["mcpServers"]["other-server"]["command"], "other")
            # Moshu added
            self.assertIn("moshu", config["mcpServers"])
            # Other settings preserved
            self.assertEqual(config["theme"], "dark")
            # Backup created
            self.assertTrue(list(config_dir.glob("config.json.bak-*")))

    def test_opencode_config_updates_existing_moshu(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_path = config_dir / "config.json"
            config_path.write_text(
                json.dumps({
                    "mcpServers": {
                        "moshu": {
                            "command": "old-command",
                            "args": ["old"],
                        }
                    }
                }),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"OPENCODE_HOME": str(config_dir), "MOSHU_DISABLE_AUTO_MCP_SETUP": ""}):
                with patch("app.services.external_agent.mcp_auto_config.shutil.which", return_value=None):
                    mcp_auto_config.auto_configure_mcp_for_provider("opencode_cli")

            config = json.loads(config_path.read_text(encoding="utf-8"))
            # Old entry replaced
            self.assertNotEqual(config["mcpServers"]["moshu"]["command"], "old-command")
            self.assertIn("--permission-pack", config["mcpServers"]["moshu"]["args"])


if __name__ == "__main__":
    unittest.main()
