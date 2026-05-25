"""Regression tests for the project cataloging service layer."""

import json
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import (
    Base,
    CatalogingCandidate,
    Chapter,
    Character,
    Project,
    WorldbuildingEntry,
)
from app.services.cataloging.applier import apply_candidates_for_run
from app.services.cataloging.job_control import (
    cancel_job,
    first_blocking_run,
    mark_run_skipped,
    pause_job,
    refresh_job_progress,
    reset_run_for_retry,
    resume_job,
)
from app.services.cataloging.manual_ops import create_manual_candidate, has_usable_chapter_summary, recover_failed_run_for_review
from app.services.cataloging.orchestrator import create_cataloging_job


class CatalogingServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_apply_candidates_updates_project_knowledge(self):
        db = self.Session()
        try:
            project = Project(title="Cataloging Project")
            db.add(project)
            db.flush()
            chapter = Chapter(
                project_id=project.id,
                title="第1章 开端",
                content="张三来到青云宗。",
            )
            db.add(chapter)
            db.commit()

            job = create_cataloging_job(db, project.id, "auto", None, [])
            run = job.chapter_runs[0]
            for item_type, payload in [
                ("chapter_summary", {"summary_text": "张三来到青云宗。", "key_events": ["张三抵达青云宗"]}),
                ("outline_create", {"title": "第1章 开端", "summary": "张三来到青云宗。", "related_characters": ["张三"]}),
                ("character_create", {"name": "张三", "role_type": "protagonist", "current_location": "青云宗"}),
                ("worldbuilding_create", {"dimension": "geography", "title": "青云宗", "content": "修行宗门。"}),
                ("chapter_link", {"character_names": ["张三"], "worldbuilding_titles": ["青云宗"], "outline_title": "第1章 开端"}),
            ]:
                db.add(CatalogingCandidate(
                    job_id=job.id,
                    chapter_run_id=run.id,
                    project_id=project.id,
                    chapter_id=chapter.id,
                    item_type=item_type,
                    raw_payload=json.dumps(payload, ensure_ascii=False),
                ))
            db.commit()

            events = apply_candidates_for_run(db, job, run)

            self.assertEqual([event["type"] for event in events], ["candidate_applied"] * 5)
            self.assertEqual(db.query(Character).count(), 1)
            self.assertEqual(db.query(WorldbuildingEntry).count(), 1)
            self.assertIsNotNone(chapter.summary)
            self.assertEqual(chapter.summary.summary_text, "张三来到青云宗。")
            self.assertIsNotNone(chapter.outline_node_id)
        finally:
            db.close()

    def test_retry_failed_run_clears_candidates_and_resets_job(self):
        db = self.Session()
        try:
            project = Project(title="Retry Project")
            db.add(project)
            db.flush()
            chapter = Chapter(project_id=project.id, title="Retry Chapter", content="content")
            db.add(chapter)
            db.commit()

            job = create_cataloging_job(db, project.id, "auto", None, [])
            run = job.chapter_runs[0]
            run.status = "failed"
            run.error = "parse failed"
            job.status = "paused_on_failure"
            job.blocked_chapter_id = run.chapter_id
            db.add(CatalogingCandidate(
                job_id=job.id,
                chapter_run_id=run.id,
                project_id=project.id,
                chapter_id=chapter.id,
                item_type="chapter_summary",
                raw_payload=json.dumps({"summary_text": "old"}, ensure_ascii=False),
            ))
            db.commit()

            reset_run_for_retry(db, job, first_blocking_run(db, job))
            db.commit()

            self.assertEqual(run.status, "pending")
            self.assertIsNone(run.error)
            self.assertEqual(job.status, "running")
            self.assertIsNone(job.blocked_chapter_id)
            self.assertEqual(db.query(CatalogingCandidate).count(), 0)
        finally:
            db.close()

    def test_skip_and_cancel_update_job_state(self):
        db = self.Session()
        try:
            project = Project(title="Control Project")
            db.add(project)
            db.flush()
            chapter = Chapter(project_id=project.id, title="Control Chapter", content="content")
            db.add(chapter)
            db.commit()

            job = create_cataloging_job(db, project.id, "manual", None, [])
            run = job.chapter_runs[0]
            run.status = "awaiting_confirmation"
            job.status = "waiting_confirmation"
            job.blocked_chapter_id = run.chapter_id
            db.commit()

            mark_run_skipped(db, job, first_blocking_run(db, job))
            db.commit()

            self.assertEqual(run.status, "skipped_by_user")
            self.assertEqual(job.status, "running")
            self.assertIsNone(job.blocked_chapter_id)
            self.assertEqual(job.context_integrity, "skipped_chapter")

            cancel_job(job)
            db.commit()

            self.assertEqual(job.status, "cancelled")
            self.assertIsNone(job.current_chapter_id)
            self.assertIsNone(job.blocked_chapter_id)
            self.assertIsNotNone(job.completed_at)
        finally:
            db.close()

    def test_manual_repair_can_recover_failed_run_for_review(self):
        db = self.Session()
        try:
            project = Project(title="Repair Project")
            db.add(project)
            db.flush()
            chapter = Chapter(project_id=project.id, title="Repair Chapter", content="content")
            db.add(chapter)
            db.commit()

            job = create_cataloging_job(db, project.id, "manual", None, [])
            run = job.chapter_runs[0]
            run.status = "failed"
            run.error = "bad jsonl"
            job.status = "paused_on_failure"
            job.blocked_chapter_id = run.chapter_id
            db.commit()

            self.assertFalse(has_usable_chapter_summary(db, run))
            create_manual_candidate(
                db,
                job,
                run,
                "chapter_summary",
                {"summary_text": "manual summary", "key_events": ["fixed"]},
                "edited",
            )
            self.assertTrue(has_usable_chapter_summary(db, run))

            recover_failed_run_for_review(db, job, run)
            db.commit()

            self.assertEqual(run.status, "awaiting_confirmation")
            self.assertIsNone(run.error)
            self.assertEqual(job.status, "waiting_confirmation")
            self.assertEqual(job.blocked_chapter_id, run.chapter_id)
        finally:
            db.close()

    def test_refresh_job_progress_flushes_pending_run_status(self):
        db = self.Session()
        try:
            project = Project(title="Progress Project")
            db.add(project)
            db.flush()
            chapter = Chapter(project_id=project.id, title="Progress Chapter", content="content")
            db.add(chapter)
            db.commit()

            job = create_cataloging_job(db, project.id, "manual", None, [])
            run = job.chapter_runs[0]
            run.status = "completed"

            refresh_job_progress(db, job)

            self.assertEqual(job.completed_chapters, 1)
        finally:
            db.close()

    def test_pause_and_resume_job(self):
        db = self.Session()
        try:
            project = Project(title="Pause Project")
            db.add(project)
            db.flush()
            chapter = Chapter(project_id=project.id, title="Pause Chapter", content="content")
            db.add(chapter)
            db.commit()

            job = create_cataloging_job(db, project.id, "auto", None, [])
            pause_job(job)
            self.assertEqual(job.status, "paused")
            resume_job(job)
            self.assertEqual(job.status, "running")
            self.assertIsNone(job.error)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
