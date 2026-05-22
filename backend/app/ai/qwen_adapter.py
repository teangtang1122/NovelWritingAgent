"""通义千问 (Qwen) adapter — uses OpenAI-compatible API format via DashScope."""
from typing import AsyncGenerator, Optional

from openai import APIError, APITimeoutError, APIConnectionError, AuthenticationError

from .base import BaseAdapter
from .openai_adapter import create_openai_compatible_client
from ..core.exceptions import LLMError


class QwenAdapter(BaseAdapter):
    """Adapter for 通义千问 (Qwen) API via DashScope (OpenAI-compatible)."""

    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    @property
    def provider_name(self) -> str:
        return "qwen"

    def _get_client(self):
        return create_openai_compatible_client(
            self.api_key,
            self.base_url or self.DEFAULT_BASE_URL,
        )

    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_body: Optional[dict] = None,
    ) -> dict:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
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
            raise LLMError(f"通义千问 API Key 无效: {e}")
        except APITimeoutError as e:
            raise LLMError(f"通义千问 请求超时: {e}")
        except APIConnectionError as e:
            raise LLMError(f"通义千问 连接错误: {e}")
        except APIError as e:
            raise LLMError(f"通义千问 API 错误: {e}")
        except Exception as e:
            raise LLMError(f"通义千问 调用失败: {e}")

    async def stream_chat_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_body: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except AuthenticationError as e:
            raise LLMError(f"通义千问 API Key 无效: {e}")
        except APITimeoutError as e:
            raise LLMError(f"通义千问 请求超时: {e}")
        except APIConnectionError as e:
            raise LLMError(f"通义千问 连接错误: {e}")
        except APIError as e:
            raise LLMError(f"通义千问 API 错误: {e}")
        except Exception as e:
            raise LLMError(f"通义千问 流式调用失败: {e}")
