"""End-to-end test for external no-API cataloging (EAC-0502).

Proves that a novel can be cataloged without Moshu LLM calls by using
the external cataloging tools directly with test-provided data.
"""
import asyncio
import json
import os
import sys
import unittest

os.environ["DATABASE_URL"] = "sqlite:///./test_external_cataloging_e2e.db"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import (
    Base,
    Project,
    Chapter,
    CatalogingJob,
    CatalogingChapterRun,
    CatalogingFact,
    CatalogingCandidate,
)

engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class ExternalCatalogingE2ETest(unittest.TestCase):
    """End-to-end external cataloging without Moshu LLM calls."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        try:
            os.remove("./test_external_cataloging_e2e.db")
        except OSError:
            pass

    def setUp(self):
        self.db = TestSession()
        self.project = Project(title="Test Novel", description="E2E test project")
        self.db.add(self.project)
        self.db.flush()

        self.chapters = []
        for i in range(1, 4):
            ch = Chapter(
                project_id=self.project.id,
                title=f"Chapter {i}",
                content=f"Content of chapter {i}. Alice appears in a mystical forest.",
                word_count=100,
            )
            self.db.add(ch)
            self.chapters.append(ch)
        self.db.commit()
        for ch in self.chapters:
            self.db.refresh(ch)

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_full_cataloging_workflow(self):
        """Full external cataloging: start -> get chapter -> save facts -> save candidates -> verify."""
        from app.services.workspace.tools.external_cataloging import (
            start_external_cataloging_job,
            get_next_external_cataloging_chapter,
            save_external_cataloging_facts,
            save_external_cataloging_candidates,
            verify_external_cataloging_progress,
        )

        project_id = self.project.id

        # Step 1: Start job
        result = _run(start_external_cataloging_job(self.db, project_id, {}))
        self.assertEqual(result["status"], "ok", f"start_job failed: {result}")
        job_id = result["data"]["job_id"]
        self.assertEqual(result["data"]["chapter_count"], 3)

        # Step 2: Process each chapter
        for i in range(3):
            result = _run(get_next_external_cataloging_chapter(self.db, project_id, {"job_id": job_id}))
            self.assertEqual(result["status"], "ok", f"get_next_chapter {i} failed: {result}")
            self.assertFalse(result["data"].get("all_done"))
            chapter_id = result["data"]["chapter_id"]

            # Save facts
            facts = [
                {"type": "character_appearance", "data": {"name": "Alice"}},
                {"type": "setting", "data": {"location": "mystical forest"}},
            ]
            result = _run(save_external_cataloging_facts(
                self.db, project_id,
                {"job_id": job_id, "chapter_id": chapter_id, "facts": facts},
            ))
            self.assertEqual(result["status"], "ok", f"save_facts {i} failed: {result}")
            self.assertEqual(result["data"]["facts_saved"], 2)

            # Save candidates
            candidates = [
                {"type": "character_create", "action": "create", "name": "Alice",
                 "personality": "brave", "background": "traveler"},
                {"type": "outline_create", "action": "create",
                 "title": f"Chapter {i + 1}", "summary": f"Summary {i + 1}"},
                {"type": "chapter_summary", "action": "create",
                 "summary": f"Chapter {i + 1} summary"},
            ]
            result = _run(save_external_cataloging_candidates(
                self.db, project_id,
                {"job_id": job_id, "chapter_id": chapter_id, "candidates": candidates},
            ))
            self.assertEqual(result["status"], "ok", f"save_candidates {i} failed: {result}")
            self.assertEqual(result["data"]["candidates_saved"], 3)

        # Step 3: Verify progress
        result = _run(verify_external_cataloging_progress(self.db, project_id, {"job_id": job_id}))
        self.assertEqual(result["status"], "ok")
        data = result["data"]
        self.assertEqual(data["chapters_processed"], 3)
        self.assertEqual(data["chapters_total"], 3)
        self.assertEqual(data["chapters_pending"], 0)
        self.assertEqual(data["chapters_failed"], 0)
        self.assertEqual(data["pending_candidates"], 9)

    def test_no_chapters_returns_skipped(self):
        """Starting cataloging on empty project should skip."""
        from app.services.workspace.tools.external_cataloging import start_external_cataloging_job

        empty = Project(title="Empty")
        self.db.add(empty)
        self.db.commit()
        self.db.refresh(empty)

        result = _run(start_external_cataloging_job(self.db, empty.id, {}))
        self.assertEqual(result["status"], "skipped")

    def test_llm_gateway_not_called(self):
        """Verify external cataloging never calls LLMGateway."""
        from unittest.mock import patch, AsyncMock

        from app.services.workspace.tools.external_cataloging import (
            start_external_cataloging_job,
            get_next_external_cataloging_chapter,
            save_external_cataloging_facts,
            save_external_cataloging_candidates,
        )

        project_id = self.project.id

        with patch("app.ai.gateway.LLMGateway.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = AssertionError("LLM should not be called")

            result = _run(start_external_cataloging_job(self.db, project_id, {}))
            self.assertEqual(result["status"], "ok")
            job_id = result["data"]["job_id"]

            result = _run(get_next_external_cataloging_chapter(self.db, project_id, {"job_id": job_id}))
            self.assertEqual(result["status"], "ok")
            chapter_id = result["data"]["chapter_id"]

            result = _run(save_external_cataloging_facts(
                self.db, project_id,
                {"job_id": job_id, "chapter_id": chapter_id, "facts": [{"type": "test", "data": {}}]},
            ))
            self.assertEqual(result["status"], "ok")

            result = _run(save_external_cataloging_candidates(
                self.db, project_id,
                {"job_id": job_id, "chapter_id": chapter_id,
                 "candidates": [{"type": "outline_create", "action": "create", "title": "Ch1"}]},
            ))
            self.assertEqual(result["status"], "ok")

            mock_llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
