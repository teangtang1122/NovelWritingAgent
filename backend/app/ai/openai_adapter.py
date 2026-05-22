"""OpenAI adapter using the official openai SDK."""
import asyncio
from typing import AsyncGenerator, Optional

from openai import AsyncOpenAI, APIError, APITimeoutError, APIConnectionError, AuthenticationError

from .base import BaseAdapter
from ..core.exceptions import LLMError


class OpenAIClientProxy:
    """Proxy client that keeps SDK behavior and exposes a stable base_url string."""

    def __init__(self, client: AsyncOpenAI, base_url: str):
        self._client = client
        self.base_url = base_url.rstrip("/")

    def __getattr__(self, name: str):
        return getattr(self._client, name)


def create_openai_compatible_client(api_key: str, base_url: Optional[str] = None):
    """Create an AsyncOpenAI-compatible client with normalized display metadata."""
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = AsyncOpenAI(**kwargs)
    if base_url:
        return OpenAIClientProxy(client, base_url)
    return client


class OpenAIAdapter(BaseAdapter):
    """Adapter for OpenAI API (GPT-4, GPT-4o, etc.)."""

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_client(self) -> AsyncOpenAI:
        return create_openai_compatible_client(self.api_key, self.base_url)

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
            raise LLMError(f"OpenAI API Key 无效: {e}")
        except APITimeoutError as e:
            raise LLMError(f"OpenAI 请求超时: {e}")
        except APIConnectionError as e:
            raise LLMError(f"OpenAI 连接错误: {e}")
        except APIError as e:
            raise LLMError(f"OpenAI API 错误: {e}")
        except Exception as e:
            raise LLMError(f"OpenAI 调用失败: {e}")

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
            raise LLMError(f"OpenAI API Key 无效: {e}")
        except APITimeoutError as e:
            raise LLMError(f"OpenAI 请求超时: {e}")
        except APIConnectionError as e:
            raise LLMError(f"OpenAI 连接错误: {e}")
        except APIError as e:
            raise LLMError(f"OpenAI API 错误: {e}")
        except Exception as e:
            raise LLMError(f"OpenAI 流式调用失败: {e}")
