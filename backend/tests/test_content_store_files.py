"""Tests for Moshu 2.x folder-backed content store."""

import asyncio
import os
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Chapter, Character, Project, WorldbuildingEntry
from app.services.content_store import refresh_project_from_files, sync_project_to_files
from app.services.workspace.tools.project_files import (
    list_project_files,
    read_project_file,
    search_project_files,
    write_project_file,
)


class ContentStoreFileSourceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_root = os.environ.get("MOSHU_CONTENT_ROOT")
        os.environ["MOSHU_CONTENT_ROOT"] = self.tmp.name
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        if self.old_root is None:
            os.environ.pop("MOSHU_CONTENT_ROOT", None)
        else:
            os.environ["MOSHU_CONTENT_ROOT"] = self.old_root
        self.tmp.cleanup()

    def _project(self) -> Project:
        project = Project(title="中文作品", description="测试")
        self.db.add(project)
        self.db.flush()
        return project

    def test_sync_and_refresh_chapter_markdown(self):
        project = self._project()
        chapter = Chapter(project_id=project.id, title="第一章 初醒", content="特昂糖睁开眼。", word_count=7)
        self.db.add(chapter)
        self.db.flush()

        sync_project_to_files(self.db, project.id)
        self.db.flush()

        path = os.path.join(project.folder_path, chapter.content_file_path)
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("第一章 初醒", text)
        self.assertIn("特昂糖睁开眼。", text)

        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text.replace("特昂糖睁开眼。", "特昂糖看见石狮子。"))

        refresh_project_from_files(self.db, project.id)
        self.assertEqual(chapter.content.strip(), "特昂糖看见石狮子。")

    def test_project_file_tools_read_write_search(self):
        project = self._project()
        self.db.add(Character(project_id=project.id, name="特昂糖", background="陆家女儿"))
        self.db.add(WorldbuildingEntry(project_id=project.id, dimension="culture", title="陆家", content="修仙家族"))
        self.db.flush()
        sync_project_to_files(self.db, project.id)

        result = asyncio.run(write_project_file(
            self.db,
            project.id,
            {"path": "outbox/note.txt", "content": "青石村求救"},
        ))
        self.assertEqual(result["status"], "ok")

        listing = asyncio.run(list_project_files(self.db, project.id, {"path": "outbox"}))
        self.assertEqual(listing["status"], "ok")
        self.assertEqual(listing["data"]["items"][0]["path"], "outbox/note.txt")

        read = asyncio.run(read_project_file(self.db, project.id, {"path": "outbox/note.txt"}))
        self.assertIn("青石村", read["data"]["content"])

        search = asyncio.run(search_project_files(self.db, project.id, {"query": "青石村"}))
        self.assertEqual(search["status"], "ok")
        self.assertEqual(len(search["data"]["matches"]), 1)
