"""Tests for scheduled task API response compatibility."""

import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///./test_scheduler.db"

from fastapi.testclient import TestClient

from app.database.models import Project, ScheduledTask
from app.database.session import Base, SessionLocal, engine
from app.main import app

API_PREFIX = "/api/v1"


class SchedulerAPITestCase(unittest.TestCase):
    """Integration tests for scheduled task API endpoints."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        try:
            os.remove("test_scheduler.db")
        except OSError:
            pass

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(ScheduledTask).delete()
            db.query(Project).delete()
            db.commit()
        finally:
            db.close()

    def create_project(self) -> str:
        response = self.client.post(f"{API_PREFIX}/projects", json={"title": "自动任务测试作品"})
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]["id"]

    def test_list_scheduled_tasks_uses_api_response_wrapper(self):
        project_id = self.create_project()

        response = self.client.get(f"{API_PREFIX}/projects/{project_id}/scheduled-tasks")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["items"], [])
        self.assertEqual(body["data"]["total"], 0)

    def test_create_scheduled_task_uses_api_response_wrapper(self):
        project_id = self.create_project()

        response = self.client.post(
            f"{API_PREFIX}/projects/{project_id}/scheduled-tasks",
            json={
                "name": "每日灵感整理",
                "prompt": "整理今日收集到的写作灵感。",
                "interval_minutes": 60,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["name"], "每日灵感整理")
        self.assertEqual(body["data"]["interval_minutes"], 60)

