"""Tests for create-novel intent in plan agent."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.agent.planner import detect_intent, build_plan_from_intent


class DetectCreateNovelIntentTest(unittest.TestCase):
    """Verify create_novel intent detection."""

    def test_detects_open_book(self):
        intent = detect_intent("帮我开一本仙侠小说")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent_type"], "create_novel")

    def test_detects_new_novel(self):
        intent = detect_intent("创建新小说")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent_type"], "create_novel")

    def test_detects_write_book(self):
        intent = detect_intent("帮我写一本都市小说")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent_type"], "create_novel")

    def test_detects_from_scratch(self):
        intent = detect_intent("从零开始写一本小说")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["intent_type"], "create_novel")

    def test_does_not_detect_chapter_writing(self):
        intent = detect_intent("帮我写第三章")
        if intent:
            self.assertNotEqual(intent["intent_type"], "create_novel")


class BuildCreateNovelPlanTest(unittest.TestCase):
    """Verify create_novel plan building."""

    def test_builds_plan(self):
        intent = {"intent_type": "create_novel", "requirements": "仙侠小说"}
        plan = build_plan_from_intent(intent)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "create_novel")

    def test_plan_has_required_steps(self):
        intent = {"intent_type": "create_novel", "requirements": "仙侠小说"}
        plan = build_plan_from_intent(intent)
        step_names = set(plan.steps.keys())
        self.assertIn("start_session", step_names)
        self.assertIn("draft_blueprints", step_names)
        self.assertIn("review_blueprint", step_names)
        self.assertIn("apply_blueprint", step_names)

    def test_plan_steps_have_dependencies(self):
        intent = {"intent_type": "create_novel", "requirements": "仙侠小说"}
        plan = build_plan_from_intent(intent)
        self.assertEqual(plan.steps["draft_blueprints"].depends_on, ["start_session"])
        self.assertEqual(plan.steps["review_blueprint"].depends_on, ["draft_blueprints"])
        self.assertEqual(plan.steps["apply_blueprint"].depends_on, ["review_blueprint"])


if __name__ == "__main__":
    unittest.main()
