"""Local runtime, catalog, routing, and dataset regression tests."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.gateway import LLMGateway
from app.database.models import (
    Base,
    Chapter,
    LocalModelTaskSetting,
    Project,
)
from app.services.local_runtime.datasets import build_training_dataset
from app.services.local_runtime.hardware import detect_hardware
from app.services.local_runtime.manifest import model_catalog
from app.services.local_runtime.manager import LocalRuntimeManager


def test_hardware_profile_has_safe_recommendation():
    profile = detect_hardware()
    assert profile.recommended_model in {"qwen3-4b-q4", "qwen3-8b-q4", "qwen3-14b-q4"}
    assert profile.recommended_context in {8192, 16384, 32768}
    assert profile.cpu_count >= 1


def test_embedded_catalog_contains_three_qwen_tiers():
    items = model_catalog()
    assert [item["model_key"] for item in items] == [
        "qwen3-4b-q4",
        "qwen3-8b-q4",
        "qwen3-14b-q4",
    ]
    assert all(len(item["sources"]) >= 2 for item in items)


def test_task_setting_routes_unspecified_model_to_local_runtime():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        db.add(LocalModelTaskSetting(task_type="writing", model_key="qwen3-8b-q4"))
        db.commit()

    with patch("app.ai.gateway.SessionLocal", Session):
        selected = LLMGateway._model_for_task(None, {"moshu_task_type": "writing"})
    assert selected == "local_llama_cpp:qwen3-8b-q4"
    assert LLMGateway._model_for_task("deepseek:custom", {"moshu_task_type": "writing"}) == "deepseek:custom"


def test_local_runtime_server_uses_single_parallel_slot():
    command = LocalRuntimeManager._build_command(
        "llama-server.exe",
        "model.gguf",
        "qwen3-8b-q4",
        8765,
        32768,
        8,
        99,
        [SimpleNamespace(file_path="adapter.gguf", weight=0.75)],
    )
    parallel_index = command.index("--parallel")
    assert command[parallel_index + 1] == "1"
    assert "--lora-scaled" in command


def test_training_dataset_deduplicates_and_splits():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    content = "第一段。" * 120 + "\n“你终于来了，我已经在这里等了整整三天。”\n“先别说话，门外的东西还没有走远。”" * 20
    with TemporaryDirectory() as temp_dir, Session() as db:
        project = Project(id="p1", title="测试作品", folder_path=temp_dir)
        db.add(project)
        db.add_all([
            Chapter(id="c1", project_id="p1", title="第一章", content=content, word_count=len(content)),
            Chapter(id="c2", project_id="p1", title="第二章", content=content + "第二章变化。", word_count=len(content)),
        ])
        db.commit()
        with patch("app.services.local_runtime.datasets.training_root", return_value=Path(temp_dir)):
            dataset = build_training_dataset(
                db,
                name="测试训练集",
                project_id="p1",
                chapter_ids=[],
                include_outline_pairs=True,
                include_revision_pairs=False,
                include_character_dialogue=True,
                eval_ratio=0.2,
                rights_confirmed=True,
            )
            db.commit()
            lines = [
                json.loads(line)
                for line in Path(dataset.file_path).read_text(encoding="utf-8").splitlines()
            ]
    assert dataset.sample_count == len(lines)
    assert dataset.train_count + dataset.eval_count == dataset.sample_count
    assert {item["split"] for item in lines} == {"train", "eval"}
