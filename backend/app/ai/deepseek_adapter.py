"""DeepSeek adapter — uses OpenAI-compatible API format."""
from typing import AsyncGenerator, Optional

from openai import APIError, APITimeoutError, APIConnectionError, AuthenticationError

from .base import BaseAdapter
from .openai_adapter import create_openai_compatible_client
from ..core.exceptions import LLMError


class DeepSeekAdapter(BaseAdapter):
    """Adapter for DeepSeek API (OpenAI-compatible)."""

    DEFAULT_BASE_URL = "https://api.deepseek.com"
    SUPPORTED_MODELS = {"deepseek-v4-pro", "deepseek-v4-flash"}
    LEGACY_MODEL_ALIASES = {"deepseek-v3": "deepseek-v4-flash"}

    @property
    def provider_name(self) -> str:
        return "deepseek"

    def _get_client(self):
        return create_openai_compatible_client(
            self.api_key,
            self.base_url or self.DEFAULT_BASE_URL,
        )

    def _normalize_model(self, model: str) -> str:
        normalized = self.LEGACY_MODEL_ALIASES.get(model, model)
        if normalized.startswith("deepseek-") and normalized not in self.SUPPORTED_MODELS:
            supported = "、".join(sorted(self.SUPPORTED_MODELS))
            raise LLMError(f"DeepSeek 当前支持的模型为 {supported}，请在系统设置中重新选择")
        return normalized

    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_body: Optional[dict] = None,
    ) -> dict:
        client = self._get_client()
        model = self._normalize_model(model)
        kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        if extra_body:
            kwargs["extra_body"] = extra_body
        try:
            response = await client.chat.completions.create(**kwargs)
            return {
                "content": response.choices[0].message.content or "",
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
            }
        except AuthenticationError as e:
            raise LLMError(f"DeepSeek API Key 无效: {e}")
        except APITimeoutError as e:
            raise LLMError(f"DeepSeek 请求超时: {e}")
        except APIConnectionError as e:
            raise LLMError(f"DeepSeek 连接错误: {e}")
        except APIError as e:
            raise LLMError(f"DeepSeek API 错误: {e}")
        except Exception as e:
            raise LLMError(f"DeepSeek 调用失败: {e}")

    async def stream_chat_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_body: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        model = self._normalize_model(model)
        kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=True)
        if extra_body:
            kwargs["extra_body"] = extra_body
        try:
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except AuthenticationError as e:
            raise LLMError(f"DeepSeek API Key 无效: {e}")
        except APITimeoutError as e:
            raise LLMError(f"DeepSeek 请求超时: {e}")
        except APIConnectionError as e:
            raise LLMError(f"DeepSeek 连接错误: {e}")
        except APIError as e:
            raise LLMError(f"DeepSeek API 错误: {e}")
        except Exception as e:
            raise LLMError(f"DeepSeek 流式调用失败: {e}")
