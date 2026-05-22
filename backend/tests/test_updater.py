"""Tests for packaged app updater helpers."""

import unittest

from app.updater import is_newer_version


class UpdaterVersionTestCase(unittest.TestCase):
    def test_semver_comparison(self):
        self.assertTrue(is_newer_version("0.1.2", "0.1.1"))
        self.assertTrue(is_newer_version("v1.0.0", "0.9.9"))
        self.assertFalse(is_newer_version("0.1.1", "0.1.1"))
        self.assertFalse(is_newer_version("0.1.0", "0.1.1"))
        self.assertFalse(is_newer_version("", "0.1.1"))


if __name__ == "__main__":
    unittest.main()
