"""Tests for project-level AI writing style guard."""

import os
import unittest
from types import SimpleNamespace

os.environ["DATABASE_URL"] = "sqlite:///./test_novel_agent.db"

from app.routers.ai_writer import (
    _detect_forbidden_sentence_violations,
    _mechanical_repair_forbidden_sentences,
)


class StyleGuardTests(unittest.TestCase):
    def setUp(self):
        self.project = SimpleNamespace(
            forbidden_sentence_patterns="\n".join([
                "不是……是……",
                "不是……而是……",
                "不是……却是……",
                "与其说……不如说……",
            ])
        )

    def test_detects_cross_sentence_not_is_pattern(self):
        text = "陆承宇低声道：“不是传播。是在回收。”特昂糖没有反驳。"

        violations = _detect_forbidden_sentence_violations(text, self.project)

        self.assertTrue(any(item["pattern"] == "不是……是……" for item in violations))

    def test_detects_comma_not_is_pattern(self):
        text = "这不是普通的血魔附体，是病毒做主了。"

        violations = _detect_forbidden_sentence_violations(text, self.project)

        self.assertTrue(any(item["pattern"] == "不是……是……" for item in violations))

    def test_detects_not_but_is_pattern(self):
        text = "这不是阵法失控，而是有人在外面计算阵眼。"

        violations = _detect_forbidden_sentence_violations(text, self.project)

        self.assertTrue(any(item["pattern"] == "不是……而是……" for item in violations))

    def test_ignores_question_form(self):
        text = "陆景珩问：“是不是阵法还能撑六个时辰？”"

        violations = _detect_forbidden_sentence_violations(text, self.project)

        self.assertFalse(violations)

    def test_mechanical_repair_removes_builtin_pattern(self):
        text = "陆承宇低声道：“不是传播。是在回收。”"

        repaired = _mechanical_repair_forbidden_sentences(text)
        violations = _detect_forbidden_sentence_violations(repaired, self.project)

        self.assertFalse(violations)
        self.assertIn("关键在于回收", repaired)


if __name__ == "__main__":
    unittest.main()
