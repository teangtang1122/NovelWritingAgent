"""Pydantic schemas for API config and global model settings."""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class APIConfigCreate(BaseModel):
    """Schema for creating/updating an API config."""
    provider: str = Field(..., min_length=1, max_length=50, description="提供商标识")
    api_key: str = Field(..., min_length=1, description="API Key（明文，后端加密存储）")
    default_model: str = Field(..., min_length=1, max_length=100, description="默认模型名")
    base_url_override: Optional[str] = Field(None, max_length=500, description="自定义API端点")
    max_output_tokens: Optional[int] = Field(None, ge=1, le=1000000, description="该模型最大输出tokens")
    deconstruct_input_char_limit: Optional[int] = Field(None, ge=1, le=1000000, description="拆书合并输入字符上限")
    deconstruct_item_char_limit: Optional[int] = Field(None, ge=1, le=1000000, description="拆书单条内容字符上限")


class APIConfigUpdate(BaseModel):
    """Schema for updating an API config."""
    api_key: Optional[str] = Field(None, min_length=1)
    default_model: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url_override: Optional[str] = Field(None, max_length=500)
    max_output_tokens: Optional[int] = Field(None, ge=1, le=1000000)
    deconstruct_input_char_limit: Optional[int] = Field(None, ge=1, le=1000000)
    deconstruct_item_char_limit: Optional[int] = Field(None, ge=1, le=1000000)


class APIConfigItem(BaseModel):
    """Schema for API config list item (without api_key)."""
    id: str
    provider: str
    default_model: str
    is_global_default: bool
    base_url_override: Optional[str]
    max_output_tokens: Optional[int] = None
    effective_max_output_tokens: Optional[int] = None
    deconstruct_input_char_limit: Optional[int] = None
    effective_deconstruct_input_char_limit: Optional[int] = None
    deconstruct_item_char_limit: Optional[int] = None
    effective_deconstruct_item_char_limit: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class APIConfigDetail(APIConfigItem):
    """Schema for API config detail (with masked api_key)."""
    api_key_masked: str = Field(..., description="脱敏后的API Key")


class GlobalModelSetting(BaseModel):
    """Schema for global default model setting."""
    provider: str = Field(..., description="全局默认提供商")
    model: str = Field(..., description="全局默认模型名")


class ChatCompletionRequest(BaseModel):
    """Schema for LLM chat completion request."""
    messages: list[dict] = Field(..., description="消息列表")
    model: Optional[str] = Field(None, description="模型标识，null则使用全局默认")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    stream: bool = Field(False, description="是否流式输出")


class ChatCompletionResponse(BaseModel):
    """Schema for LLM chat completion response (non-streaming)."""
    content: str
    model: str
    usage: Optional[dict] = None


class ModelListRequest(BaseModel):
    """Schema for requesting available models from a provider."""
    provider: str = Field(..., min_length=1, max_length=50, description="提供商标识")
    api_key: str = Field(..., min_length=1, description="API Key（明文）")
    base_url_override: Optional[str] = Field(None, max_length=500, description="自定义API端点")


class ConnectionTestRequest(BaseModel):
    """Schema for testing API connection."""
    provider: str = Field(..., min_length=1, max_length=50, description="提供商标识")
    api_key: str = Field(..., min_length=1, description="API Key（明文）")
    base_url_override: Optional[str] = Field(None, max_length=500, description="自定义API端点")
