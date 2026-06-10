"""Tests for tool result contract in prompt packs (EAC-0401).

Verifies that external-agent prompt packs include rules preventing
agents from reporting "done" after failed or skipped writes.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.prompt_packs.seed import BUILTIN_PACKS


def _get_cataloging_pack() -> dict:
    return next(p for p in BUILTIN_PACKS if p["pack_id"] == "cataloging_external_no_api")


class ToolResultContractTest(unittest.TestCase):
    """Verify prompt packs enforce tool result contract rules."""

    def test_requires_status_check(self):
        """Pack must instruct agent to check status after every tool call."""
        prompt = _get_cataloging_pack()["system_prompt"]
        self.assertIn("status", prompt)
        self.assertTrue(
            "status" in prompt and ("ok" in prompt or "失败" in prompt),
            "Pack should instruct agent to check tool status",
        )

    def test_requires_stop_on_failure(self):
        """Pack must instruct agent to stop and report on failure."""
        prompt = _get_cataloging_pack()["system_prompt"]
        self.assertTrue(
            "停止" in prompt or "报告" in prompt or "失败" in prompt,
            "Pack should instruct agent to stop on failure",
        )

    def test_requires_verification_after_write(self):
        """Pack must require read/verify after write operations."""
        prompt = _get_cataloging_pack()["system_prompt"]
        self.assertIn("验证", prompt)
        self.assertIn("verify_external_cataloging_progress", prompt)

    def test_requires_nonzero_counts_for_completion(self):
        """Pack must require nonzero counts before reporting done."""
        prompt = _get_cataloging_pack()["system_prompt"]
        self.assertTrue(
            "章节数" in prompt or "章节" in prompt,
            "Pack should mention chapter count requirement",
        )
        self.assertTrue(
            "大纲" in prompt,
            "Pack should mention outline count requirement",
        )
        self.assertTrue(
            "角色" in prompt,
            "Pack should mention character count requirement",
        )

    def test_forbids_reporting_done_without_verification(self):
        """Pack must forbid reporting complete without verification."""
        forbidden = _get_cataloging_pack().get("forbidden_patterns_json", [])
        combined = " ".join(forbidden)
        self.assertTrue(
            "完成" in combined or "验证" in combined,
            "Forbidden patterns should include rule about not reporting done without verification",
        )

    def test_forbids_skipping_verification(self):
        """Pack must forbid skipping read-write verification."""
        forbidden = _get_cataloging_pack().get("forbidden_patterns_json", [])
        combined = " ".join(forbidden)
        self.assertTrue(
            "验证" in combined,
            "Forbidden patterns should include rule about not skipping verification",
        )


class WorkflowVerificationStepsTest(unittest.TestCase):
    """Verify workflow includes verification steps."""

    def test_workflow_has_verify_step(self):
        """Workflow must include a verify/progress step."""
        workflow = _get_cataloging_pack().get("workflow_json", [])
        step_names = [s.get("name", "") for s in workflow]
        self.assertTrue(
            any("verify" in name for name in step_names),
            f"Workflow should include a verify step, got: {step_names}",
        )

    def test_workflow_verify_after_save(self):
        """Verify step must come after save steps."""
        workflow = _get_cataloging_pack().get("workflow_json", [])
        steps = [(s.get("step", 0), s.get("name", "")) for s in workflow]
        save_indices = [i for i, (_, name) in enumerate(steps) if "save" in name]
        verify_indices = [i for i, (_, name) in enumerate(steps) if "verify" in name]
        if save_indices and verify_indices:
            self.assertGreater(min(verify_indices), max(save_indices),
                "Verify step should come after save steps")

    def test_workflow_has_final_verify(self):
        """Workflow must include a final verification step."""
        workflow = _get_cataloging_pack().get("workflow_json", [])
        step_names = [s.get("name", "") for s in workflow]
        self.assertTrue(
            any("final" in name and "verify" in name for name in step_names),
            f"Workflow should include final verify step, got: {step_names}",
        )


if __name__ == "__main__":
    unittest.main()
