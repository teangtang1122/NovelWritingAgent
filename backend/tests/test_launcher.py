"""Tests for packaged launcher data-directory compatibility."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import launcher


class LauncherDataDirectoryTestCase(unittest.TestCase):
    def test_uses_legacy_data_directory_when_current_database_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            legacy = base / "NovelWritingAgent"
            legacy.mkdir()
            (legacy / "novel_agent.db").write_bytes(b"legacy database")

            with patch.dict(
                "os.environ",
                {"LOCALAPPDATA": str(base), "USERPROFILE": str(base)},
                clear=True,
            ):
                self.assertEqual(launcher._app_home(), legacy)

    def test_uses_moshu_home_when_explicitly_configured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "custom"
            with patch.dict("os.environ", {"MOSHU_HOME": str(home)}, clear=True):
                self.assertEqual(launcher._app_home(), home.resolve())

    def test_prepare_data_environment_sets_database_url_for_legacy_home(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            legacy = base / "NovelWritingAgent"
            legacy.mkdir()
            (legacy / "novel_agent.db").write_bytes(b"legacy database")

            with patch.dict(
                "os.environ",
                {"LOCALAPPDATA": str(base), "USERPROFILE": str(base)},
                clear=True,
            ):
                home = launcher._prepare_data_environment()

                self.assertEqual(home, legacy)
                self.assertEqual(
                    os.environ["DATABASE_URL"],
                    f"sqlite:///{(legacy / 'novel_agent.db').as_posix()}",
                )
                self.assertEqual(os.environ["MOSHU_HOME"], str(legacy))
                self.assertEqual(os.environ["NOVEL_AGENT_HOME"], str(legacy))


if __name__ == "__main__":
    unittest.main()
