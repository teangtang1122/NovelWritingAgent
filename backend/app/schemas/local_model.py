"""Schemas for the local model center and LoRA training beta."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LocalModelBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class ModelInstallRequest(LocalModelBase):
    model_key: str = Field(..., min_length=1, max_length=120)


class ModelRootUpdateRequest(LocalModelBase):
    path: str = Field(..., min_length=1, max_length=1000)


class RuntimeStartRequest(LocalModelBase):
    model_key: str = Field(..., min_length=1, max_length=120)
    context_length: Optional[int] = Field(None, ge=2048, le=131072)
    task_type: str = Field("chat", max_length=30)
    project_id: Optional[str] = Field(None, max_length=36)


class BenchmarkRequest(LocalModelBase):
    model_key: str = Field(..., min_length=1, max_length=120)
    prompt: str = Field("请用中文简短介绍你自己。", min_length=1, max_length=2000)
    max_tokens: int = Field(128, ge=8, le=2048)


class AdapterUpdateRequest(LocalModelBase):
    enabled: Optional[bool] = None
    weight: Optional[float] = Field(None, ge=-4, le=4)
    is_default_for_writing: Optional[bool] = None


class AdapterCompareRequest(LocalModelBase):
    model_key: str = Field(..., min_length=1, max_length=120)
    prompt: str = Field(..., min_length=1, max_length=8000)
    project_id: Optional[str] = Field(None, max_length=36)
    adapter_ids: list[str] = Field(default_factory=list, max_length=2)
    max_tokens: int = Field(800, ge=100, le=4000)


class DatasetCreateRequest(LocalModelBase):
    name: str = Field(..., min_length=1, max_length=200)
    project_id: Optional[str] = Field(None, max_length=36)
    chapter_ids: list[str] = Field(default_factory=list)
    include_outline_pairs: bool = True
    include_revision_pairs: bool = True
    include_character_dialogue: bool = True
    eval_ratio: float = Field(0.1, ge=0.05, le=0.3)
    rights_confirmed: bool = False


class TrainingJobCreateRequest(LocalModelBase):
    name: str = Field(..., min_length=1, max_length=200)
    dataset_id: str = Field(..., min_length=1, max_length=36)
    base_model_key: str = Field(..., min_length=1, max_length=120)
    project_id: Optional[str] = Field(None, max_length=36)
    epochs: float = Field(1.0, gt=0, le=10)
    learning_rate: float = Field(0.0002, gt=0, le=0.01)
    lora_rank: int = Field(16, ge=4, le=128)
    batch_size: int = Field(1, ge=1, le=16)
    gradient_accumulation: int = Field(8, ge=1, le=128)
    max_sequence_length: int = Field(4096, ge=512, le=16384)
