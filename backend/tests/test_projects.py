"""
Test cases for Project CRUD API endpoints (FR-008: 多作品管理).

Covers:
  - GET    /api/v1/projects          — list + search
  - POST   /api/v1/projects          — create
  - GET    /api/v1/projects/{id}     — detail
  - PUT    /api/v1/projects/{id}     — update
  - DELETE /api/v1/projects/{id}     — delete + cascade

Test design principles:
  - Does NOT rely on pre-existing database data.
  - Create-before-use: data needed by a test is created in setUp or within the test.
  - Cleanup after each test: all created data is removed in tearDown.
  - Delete-before-create for uniqueness-sensitive data (e.g., title checks).
  - Cascade-delete verification ensures data isolation between projects.
"""

import os
import json
import unittest

# ---------------------------------------------------------------------------
# MUST set test database BEFORE importing any application modules.
# The database engine and session are created at module import time,
# so we override the env var first to use a dedicated test database.
# ---------------------------------------------------------------------------
os.environ["DATABASE_URL"] = "sqlite:///./test_novel_agent.db"

from fastapi.testclient import TestClient
from app.main import app
from app.database.session import Base, engine, SessionLocal
from app.database.models import (
    Project,
    WorldbuildingEntry,
    Character,
    OutlineNode,
    Chapter,
    DeconstructionReport,
)

API_PREFIX = "/api/v1"


class TestProjectListAPI(unittest.TestCase):
    """Test cases for GET /api/v1/projects (list + search)."""

    @classmethod
    def setUpClass(cls):
        """Create test database tables once for this test class."""
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        """Drop all tables and remove the test database file."""
        Base.metadata.drop_all(bind=engine)
        try:
            os.remove("test_novel_agent.db")
        except OSError:
            pass

    def setUp(self):
        """Clean all project data before each test."""
        db = SessionLocal()
        try:
            db.query(Project).delete()
            db.commit()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # TC-01: List projects when empty
    # ------------------------------------------------------------------
    def test_list_projects_empty(self):
        """GET /projects returns empty list when no projects exist."""
        response = self.client.get(f"{API_PREFIX}/projects")
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["total"], 0)
        self.assertEqual(body["data"]["items"], [])

    # ------------------------------------------------------------------
    # TC-02: List projects with one item
    # ------------------------------------------------------------------
    def test_list_projects_single(self):
        """GET /projects returns one project after creation."""
        # Create a project first
        create_resp = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "测试作品A", "description": "一部测试小说"},
        )
        self.assertEqual(create_resp.status_code, 200)

        response = self.client.get(f"{API_PREFIX}/projects")
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["total"], 1)
        self.assertEqual(len(body["data"]["items"]), 1)
        self.assertEqual(body["data"]["items"][0]["title"], "测试作品A")

    # ------------------------------------------------------------------
    # TC-03: List projects with multiple items
    # ------------------------------------------------------------------
    def test_list_projects_multiple(self):
        """GET /projects returns all created projects."""
        titles = ["作品1", "作品2", "作品3"]
        for title in titles:
            self.client.post(f"{API_PREFIX}/projects", json={"title": title})

        response = self.client.get(f"{API_PREFIX}/projects")
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["data"]["total"], 3)
        returned_titles = {item["title"] for item in body["data"]["items"]}
        self.assertEqual(returned_titles, set(titles))

    # ------------------------------------------------------------------
    # TC-04: Search by title keyword
    # ------------------------------------------------------------------
    def test_search_by_title(self):
        """GET /projects?q=keyword returns matching projects by title."""
        self.client.post(f"{API_PREFIX}/projects", json={"title": "修仙传"})
        self.client.post(f"{API_PREFIX}/projects", json={"title": "魔法世界"})
        self.client.post(f"{API_PREFIX}/projects", json={"title": "修仙之路"})

        response = self.client.get(f"{API_PREFIX}/projects", params={"q": "修仙"})
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["data"]["total"], 2)
        titles = {item["title"] for item in body["data"]["items"]}
        self.assertIn("修仙传", titles)
        self.assertIn("修仙之路", titles)
        self.assertNotIn("魔法世界", titles)

    # ------------------------------------------------------------------
    # TC-05: Search by description keyword
    # ------------------------------------------------------------------
    def test_search_by_description(self):
        """GET /projects?q=keyword returns matching projects by description."""
        self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "作品A", "description": "这是一个关于修仙的故事"},
        )
        self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "作品B", "description": "这是一个关于魔法的故事"},
        )

        response = self.client.get(f"{API_PREFIX}/projects", params={"q": "修仙"})
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["data"]["total"], 1)
        self.assertEqual(body["data"]["items"][0]["title"], "作品A")

    # ------------------------------------------------------------------
    # TC-06: Search with no matching results
    # ------------------------------------------------------------------
    def test_search_no_results(self):
        """GET /projects?q=nonexistent returns empty list."""
        self.client.post(f"{API_PREFIX}/projects", json={"title": "测试作品"})

        response = self.client.get(f"{API_PREFIX}/projects", params={"q": "不存在的关键词"})
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["data"]["total"], 0)
        self.assertEqual(body["data"]["items"], [])

    # ------------------------------------------------------------------
    # TC-06b: Projects ordered by updated_at descending
    # ------------------------------------------------------------------
    def test_list_projects_ordered_by_updated_at_desc(self):
        """GET /projects returns projects ordered by updated_at descending."""
        resp1 = self.client.post(f"{API_PREFIX}/projects", json={"title": "旧作品"})
        resp2 = self.client.post(f"{API_PREFIX}/projects", json={"title": "新作品"})

        response = self.client.get(f"{API_PREFIX}/projects")
        body = response.json()
        items = body["data"]["items"]
        # The most recently created (新作品) should come first
        self.assertEqual(items[0]["title"], "新作品")
        self.assertEqual(items[1]["title"], "旧作品")


class TestProjectCreateAPI(unittest.TestCase):
    """Test cases for POST /api/v1/projects (create)."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        try:
            os.remove("test_novel_agent.db")
        except OSError:
            pass

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(Project).delete()
            db.commit()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # TC-07: Create project with minimal fields
    # ------------------------------------------------------------------
    def test_create_project_minimal(self):
        """POST /projects with only title succeeds."""
        response = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "最小作品"},
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["message"], "作品创建成功")
        data = body["data"]
        self.assertEqual(data["title"], "最小作品")
        self.assertIsNotNone(data["id"])
        # Default values
        self.assertEqual(data["narrative_perspective"], "third_person")
        self.assertEqual(data["writing_style"], "natural")
        self.assertEqual(data["daily_word_goal"], 6000)

    # ------------------------------------------------------------------
    # TC-08: Create project with all fields
    # ------------------------------------------------------------------
    def test_create_project_full(self):
        """POST /projects with all fields succeeds."""
        payload = {
            "title": "完整作品",
            "description": "这是一部完整的测试小说，包含所有字段",
            "tags": ["玄幻", "修仙", "热血"],
            "narrative_perspective": "first_person",
            "writing_style": "humorous",
            "daily_word_goal": 10000,
        }
        response = self.client.post(f"{API_PREFIX}/projects", json=payload)
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["code"], 0)
        data = body["data"]
        self.assertEqual(data["title"], "完整作品")
        self.assertEqual(data["description"], "这是一部完整的测试小说，包含所有字段")
        self.assertEqual(data["narrative_perspective"], "first_person")
        self.assertEqual(data["writing_style"], "humorous")
        self.assertEqual(data["daily_word_goal"], 10000)
        # tags are stored as JSON string in DB
        tags = json.loads(data["tags"])
        self.assertEqual(tags, ["玄幻", "修仙", "热血"])

    # ------------------------------------------------------------------
    # TC-09: Verify response data completeness
    # ------------------------------------------------------------------
    def test_create_project_response_fields(self):
        """POST /projects response contains all expected fields."""
        response = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "数据完整性测试"},
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()["data"]
        expected_fields = {
            "id", "title", "description", "tags",
            "narrative_perspective", "writing_style", "daily_word_goal",
            "created_at", "updated_at",
        }
        self.assertTrue(expected_fields.issubset(set(data.keys())))

    # ------------------------------------------------------------------
    # TC-10: Create with missing title (validation error)
    # ------------------------------------------------------------------
    def test_create_project_missing_title(self):
        """POST /projects without title returns validation error."""
        response = self.client.post(f"{API_PREFIX}/projects", json={})
        self.assertEqual(response.status_code, 422)

    # ------------------------------------------------------------------
    # TC-11: Create with empty title (validation error)
    # ------------------------------------------------------------------
    def test_create_project_empty_title(self):
        """POST /projects with empty title returns validation error."""
        response = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": ""},
        )
        self.assertEqual(response.status_code, 422)

    # ------------------------------------------------------------------
    # TC-12: Create with title exceeding max length
    # ------------------------------------------------------------------
    def test_create_project_title_too_long(self):
        """POST /projects with title > 200 chars returns validation error."""
        response = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "A" * 201},
        )
        self.assertEqual(response.status_code, 422)

    # ------------------------------------------------------------------
    # TC-13: Create with negative daily_word_goal
    # ------------------------------------------------------------------
    def test_create_project_negative_word_goal(self):
        """POST /projects with daily_word_goal < 0 returns validation error."""
        response = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "测试", "daily_word_goal": -1},
        )
        self.assertEqual(response.status_code, 422)


class TestProjectDetailAPI(unittest.TestCase):
    """Test cases for GET /api/v1/projects/{id} (detail)."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        try:
            os.remove("test_novel_agent.db")
        except OSError:
            pass

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(Project).delete()
            db.commit()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # TC-14: Get existing project returns correct data
    # ------------------------------------------------------------------
    def test_get_project_existing(self):
        """GET /projects/{id} returns correct project data."""
        create_resp = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "详情测试作品", "description": "用于测试详情接口"},
        )
        project_id = create_resp.json()["data"]["id"]

        response = self.client.get(f"{API_PREFIX}/projects/{project_id}")
        self.assertEqual(response.status_code, 200)

        data = response.json()["data"]
        self.assertEqual(data["id"], project_id)
        self.assertEqual(data["title"], "详情测试作品")
        self.assertEqual(data["description"], "用于测试详情接口")

    # ------------------------------------------------------------------
    # TC-15: Get non-existent project returns 404
    # ------------------------------------------------------------------
    def test_get_project_not_found(self):
        """GET /projects/{nonexistent_id} returns 404."""
        response = self.client.get(f"{API_PREFIX}/projects/non-existent-id")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], 404)
        self.assertEqual(response.json()["message"], "作品不存在")


class TestProjectUpdateAPI(unittest.TestCase):
    """Test cases for PUT /api/v1/projects/{id} (update)."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        try:
            os.remove("test_novel_agent.db")
        except OSError:
            pass

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(Project).delete()
            db.commit()
        finally:
            db.close()

    def _create_project(self, title: str = "原始标题") -> str:
        """Helper: create a project and return its id."""
        resp = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": title, "description": "原始简介"},
        )
        return resp.json()["data"]["id"]

    # ------------------------------------------------------------------
    # TC-16: Update project title
    # ------------------------------------------------------------------
    def test_update_project_title(self):
        """PUT /projects/{id} updates title successfully."""
        project_id = self._create_project()

        response = self.client.put(
            f"{API_PREFIX}/projects/{project_id}",
            json={"title": "修改后的标题"},
        )
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["message"], "作品更新成功")
        self.assertEqual(body["data"]["title"], "修改后的标题")
        # Description should remain unchanged
        self.assertEqual(body["data"]["description"], "原始简介")

    # ------------------------------------------------------------------
    # TC-17: Update project description
    # ------------------------------------------------------------------
    def test_update_project_description(self):
        """PUT /projects/{id} updates description successfully."""
        project_id = self._create_project()

        response = self.client.put(
            f"{API_PREFIX}/projects/{project_id}",
            json={"description": "新的简介"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["description"], "新的简介")
        self.assertEqual(response.json()["data"]["title"], "原始标题")

    # ------------------------------------------------------------------
    # TC-18: Update project tags
    # ------------------------------------------------------------------
    def test_update_project_tags(self):
        """PUT /projects/{id} updates tags successfully."""
        project_id = self._create_project()

        response = self.client.put(
            f"{API_PREFIX}/projects/{project_id}",
            json={"tags": ["都市", "悬疑"]},
        )
        self.assertEqual(response.status_code, 200)

        tags = json.loads(response.json()["data"]["tags"])
        self.assertEqual(tags, ["都市", "悬疑"])

    # ------------------------------------------------------------------
    # TC-19: Update multiple fields simultaneously
    # ------------------------------------------------------------------
    def test_update_project_multiple_fields(self):
        """PUT /projects/{id} updates multiple fields at once."""
        project_id = self._create_project()

        payload = {
            "title": "全面修改",
            "description": "全面更新的简介",
            "narrative_perspective": "omniscient",
            "writing_style": "serious",
            "daily_word_goal": 8000,
        }
        response = self.client.put(
            f"{API_PREFIX}/projects/{project_id}",
            json=payload,
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()["data"]
        self.assertEqual(data["title"], "全面修改")
        self.assertEqual(data["description"], "全面更新的简介")
        self.assertEqual(data["narrative_perspective"], "omniscient")
        self.assertEqual(data["writing_style"], "serious")
        self.assertEqual(data["daily_word_goal"], 8000)

    # ------------------------------------------------------------------
    # TC-20: Update with empty body (validation error)
    # ------------------------------------------------------------------
    def test_update_project_empty_body(self):
        """PUT /projects/{id} with empty body returns validation error."""
        project_id = self._create_project()

        response = self.client.put(
            f"{API_PREFIX}/projects/{project_id}",
            json={},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "未提供任何更新字段")

    # ------------------------------------------------------------------
    # TC-21: Update non-existent project returns 404
    # ------------------------------------------------------------------
    def test_update_project_not_found(self):
        """PUT /projects/{nonexistent_id} returns 404."""
        response = self.client.put(
            f"{API_PREFIX}/projects/non-existent-id",
            json={"title": "新标题"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["message"], "作品不存在")


class TestProjectDeleteAPI(unittest.TestCase):
    """Test cases for DELETE /api/v1/projects/{id} (delete + cascade)."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        try:
            os.remove("test_novel_agent.db")
        except OSError:
            pass

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(Project).delete()
            db.commit()
        finally:
            db.close()

    def _create_project(self, title: str = "待删除作品") -> str:
        """Helper: create a project and return its id."""
        resp = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": title},
        )
        return resp.json()["data"]["id"]

    # ------------------------------------------------------------------
    # TC-22: Delete existing project returns success
    # ------------------------------------------------------------------
    def test_delete_project_success(self):
        """DELETE /projects/{id} deletes successfully."""
        project_id = self._create_project("即将删除")

        response = self.client.delete(f"{API_PREFIX}/projects/{project_id}")
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["message"], "作品已删除")
        self.assertIsNone(body["data"])

    # ------------------------------------------------------------------
    # TC-23: Delete non-existent project returns 404
    # ------------------------------------------------------------------
    def test_delete_project_not_found(self):
        """DELETE /projects/{nonexistent_id} returns 404."""
        response = self.client.delete(f"{API_PREFIX}/projects/non-existent-id")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["message"], "作品不存在")

    # ------------------------------------------------------------------
    # TC-24: Verify project is actually removed after delete
    # ------------------------------------------------------------------
    def test_delete_project_actually_removed(self):
        """After DELETE, GET /projects/{id} returns 404."""
        project_id = self._create_project("验证删除")

        # Delete
        self.client.delete(f"{API_PREFIX}/projects/{project_id}")

        # Try to get the deleted project
        response = self.client.get(f"{API_PREFIX}/projects/{project_id}")
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # TC-25: Cascade delete — associated data removed
    # ------------------------------------------------------------------
    def test_delete_project_cascade(self):
        """Deleting a project removes all associated data (cascade)."""
        # Create a project first
        project_id = self._create_project("级联删除测试")

        # Manually insert associated data via the ORM
        db = SessionLocal()
        try:
            # Add worldbuilding entry
            wb = WorldbuildingEntry(
                project_id=project_id,
                dimension="geography",
                title="测试大陆",
                content="一片神奇的大陆",
            )
            db.add(wb)

            # Add a character
            char = Character(
                project_id=project_id,
                name="测试角色",
                role_type="protagonist",
            )
            db.add(char)
            db.flush()

            # Add an outline node
            outline = OutlineNode(
                project_id=project_id,
                node_type="chapter",
                title="第一章",
                summary="开头章节",
            )
            db.add(outline)
            db.flush()

            # Add a chapter
            chapter = Chapter(
                project_id=project_id,
                outline_node_id=outline.id,
                title="第一章",
                content="很久很久以前...",
                word_count=100,
            )
            db.add(chapter)

            # Add a deconstruction report
            report = DeconstructionReport(
                project_id=project_id,
                source_filename="test.txt",
                report_data="{}",
                status="completed",
            )
            db.add(report)

            db.commit()
        finally:
            db.close()

        # Delete the project via API
        response = self.client.delete(f"{API_PREFIX}/projects/{project_id}")
        self.assertEqual(response.status_code, 200)

        # Verify all associated data is gone
        db = SessionLocal()
        try:
            self.assertEqual(db.query(WorldbuildingEntry).filter(
                WorldbuildingEntry.project_id == project_id
            ).count(), 0)
            self.assertEqual(db.query(Character).filter(
                Character.project_id == project_id
            ).count(), 0)
            self.assertEqual(db.query(OutlineNode).filter(
                OutlineNode.project_id == project_id
            ).count(), 0)
            self.assertEqual(db.query(Chapter).filter(
                Chapter.project_id == project_id
            ).count(), 0)
            self.assertEqual(db.query(DeconstructionReport).filter(
                DeconstructionReport.project_id == project_id
            ).count(), 0)
        finally:
            db.close()


class TestProjectDataIsolation(unittest.TestCase):
    """Test cases verifying project-level data isolation (FR-008)."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        try:
            os.remove("test_novel_agent.db")
        except OSError:
            pass

    def setUp(self):
        """Clean all data before each test."""
        db = SessionLocal()
        try:
            db.query(Project).delete()
            db.commit()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # TC-26: Projects are isolated from each other
    # ------------------------------------------------------------------
    def test_projects_data_isolation(self):
        """Each project returns only its own data."""
        # Create project A
        resp_a = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "项目A"},
        )
        project_a_id = resp_a.json()["data"]["id"]

        # Create project B
        resp_b = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "项目B"},
        )
        project_b_id = resp_b.json()["data"]["id"]

        # Insert associated data for project A
        db = SessionLocal()
        try:
            db.add(Character(project_id=project_a_id, name="角色A1", role_type="protagonist"))
            db.add(Character(project_id=project_a_id, name="角色A2", role_type="supporting"))
            db.add(Character(project_id=project_b_id, name="角色B1", role_type="antagonist"))
            db.add(OutlineNode(project_id=project_a_id, node_type="chapter", title="A大纲1"))
            db.add(OutlineNode(project_id=project_b_id, node_type="chapter", title="B大纲1"))
            db.commit()
        finally:
            db.close()

        # Verify project A detail only shows project A data
        resp = self.client.get(f"{API_PREFIX}/projects/{project_a_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["title"], "项目A")

        resp = self.client.get(f"{API_PREFIX}/projects/{project_b_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["title"], "项目B")

        # Verify characters are isolated per project
        db = SessionLocal()
        try:
            chars_a = db.query(Character).filter(Character.project_id == project_a_id).all()
            chars_b = db.query(Character).filter(Character.project_id == project_b_id).all()
            self.assertEqual(len(chars_a), 2)
            self.assertEqual(len(chars_b), 1)
            self.assertEqual(chars_a[0].name, "角色A1")
            self.assertEqual(chars_b[0].name, "角色B1")
        finally:
            db.close()

    # ------------------------------------------------------------------
    # TC-27: Deleting one project does not affect another
    # ------------------------------------------------------------------
    def test_delete_project_does_not_affect_other(self):
        """Deleting project A leaves project B intact."""
        resp_a = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "项目A"},
        )
        project_a_id = resp_a.json()["data"]["id"]

        resp_b = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "项目B"},
        )
        project_b_id = resp_b.json()["data"]["id"]

        # Delete project A
        self.client.delete(f"{API_PREFIX}/projects/{project_a_id}")

        # Project B should still exist
        resp = self.client.get(f"{API_PREFIX}/projects/{project_b_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["title"], "项目B")

        # Project list should only contain project B
        list_resp = self.client.get(f"{API_PREFIX}/projects")
        self.assertEqual(list_resp.json()["data"]["total"], 1)
        self.assertEqual(list_resp.json()["data"]["items"][0]["id"], project_b_id)

    # ------------------------------------------------------------------
    # TC-28: Switching project shows correct data
    # ------------------------------------------------------------------
    def test_switch_project_shows_correct_data(self):
        """Switching between projects via GET /projects/{id} shows the correct project."""
        # Create two projects with different narratives
        resp_a = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "修仙记", "narrative_perspective": "first_person"},
        )
        project_a_id = resp_a.json()["data"]["id"]

        resp_b = self.client.post(
            f"{API_PREFIX}/projects",
            json={"title": "魔法录", "narrative_perspective": "third_person"},
        )
        project_b_id = resp_b.json()["data"]["id"]

        # Switch to project A
        resp = self.client.get(f"{API_PREFIX}/projects/{project_a_id}")
        self.assertEqual(resp.json()["data"]["title"], "修仙记")
        self.assertEqual(resp.json()["data"]["narrative_perspective"], "first_person")

        # Switch to project B
        resp = self.client.get(f"{API_PREFIX}/projects/{project_b_id}")
        self.assertEqual(resp.json()["data"]["title"], "魔法录")
        self.assertEqual(resp.json()["data"]["narrative_perspective"], "third_person")


if __name__ == "__main__":
    unittest.main(verbosity=2)
