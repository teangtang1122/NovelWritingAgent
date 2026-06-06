"""Pydantic schemas for API config and global model settings."""
from typing import Optional
import re
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


PROVIDER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_provider_id(provider: str) -> str:
    provider = provider.strip()
    if not PROVIDER_ID_PATTERN.fullmatch(provider):
        raise ValueError("提供商标识只能包含字母、数字、下划线和短横线")
    return provider


class APIConfigCreate(BaseModel):
    """Schema for creating/updating an API config."""
    provider: str = Field(..., min_length=1, max_length=50, description="提供商标识")
    api_key: str = Field(..., min_length=1, description="API Key（明文，后端加密存储）")
    default_model: str = Field(..., min_length=1, max_length=100, description="默认模型名")
    base_url_override: Optional[str] = Field(None, max_length=500, description="自定义API端点")
    max_output_tokens: Optional[int] = Field(None, ge=1, le=1000000, description="该模型最大输出tokens")
    deconstruct_input_char_limit: Optional[int] = Field(None, ge=1, le=1000000, description="拆书合并输入字符上限")
    deconstruct_item_char_limit: Optional[int] = Field(None, ge=1, le=1000000, description="拆书单条内容字符上限")

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, provider: str) -> str:
        return validate_provider_id(provider)


class GlobalModelSetting(BaseModel):
    """Schema for global default model setting."""
    provider: str = Field(..., description="全局默认提供商")
    model: str = Field(..., description="全局默认模型名")

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, provider: str) -> str:
        return validate_provider_id(provider)


class ModelListRequest(BaseModel):
    """Schema for requesting available models from a provider."""
    provider: str = Field(..., min_length=1, max_length=50, description="提供商标识")
    api_key: str = Field(..., min_length=1, description="API Key（明文）")
    base_url_override: Optional[str] = Field(None, max_length=500, description="自定义API端点")

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, provider: str) -> str:
        return validate_provider_id(provider)


class ConnectionTestRequest(BaseModel):
    """Schema for testing API connection."""
    provider: str = Field(..., min_length=1, max_length=50, description="提供商标识")
    api_key: str = Field(..., min_length=1, description="API Key（明文）")
    base_url_override: Optional[str] = Field(None, max_length=500, description="自定义API端点")

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, provider: str) -> str:
        return validate_provider_id(provider)
