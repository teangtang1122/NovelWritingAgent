"""Anthropic Claude adapter using the official anthropic SDK."""
from typing import AsyncGenerator, Optional

from anthropic import AsyncAnthropic, APIError, APITimeoutError, APIConnectionError, AuthenticationError

from .base import BaseAdapter
from ..core.exceptions import LLMError


class AnthropicAdapter(BaseAdapter):
    """Adapter for Anthropic Claude API."""

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _get_client(self) -> AsyncAnthropic:
        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return AsyncAnthropic(**kwargs)

    @staticmethod
    def _convert_messages(messages: list[dict]) -> tuple[Optional[str], list[dict]]:
        """Convert OpenAI-style messages to Anthropic format.
        
        Anthropic uses 'system' as a top-level parameter and 'user'/'assistant' in messages.
        """
        system = None
        anthropic_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system = content
            elif role in ("user", "assistant"):
                anthropic_messages.append({"role": role, "content": content})
            else:
                anthropic_messages.append({"role": "user", "content": content})
        # Ensure first message is user if no system
        if not anthropic_messages:
            anthropic_messages.append({"role": "user", "content": ""})
        return system, anthropic_messages

    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_body: Optional[dict] = None,
    ) -> dict:
        client = self._get_client()
        system, anthropic_messages = self._convert_messages(messages)
        try:
            kwargs = {
                "model": model,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
            }
            if system:
                kwargs["system"] = system

            response = await client.messages.create(**kwargs)
            return {
                "content": response.content[0].text if response.content else "",
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                    "completion_tokens": response.usage.output_tokens if response.usage else 0,
                    "total_tokens": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
                },
            }
        except AuthenticationError as e:
            raise LLMError(f"Anthropic API Key 无效: {e}")
        except APITimeoutError as e:
            raise LLMError(f"Anthropic 请求超时: {e}")
        except APIConnectionError as e:
            raise LLMError(f"Anthropic 连接错误: {e}")
        except APIError as e:
            raise LLMError(f"Anthropic API 错误: {e}")
        except Exception as e:
            raise LLMError(f"Anthropic 调用失败: {e}")

    async def stream_chat_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_body: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        system, anthropic_messages = self._convert_messages(messages)
        try:
            kwargs = {
                "model": model,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
                "stream": True,
            }
            if system:
                kwargs["system"] = system

            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    if text:
                        yield text
        except AuthenticationError as e:
            raise LLMError(f"Anthropic API Key 无效: {e}")
        except APITimeoutError as e:
            raise LLMError(f"Anthropic 请求超时: {e}")
        except APIConnectionError as e:
            raise LLMError(f"Anthropic 连接错误: {e}")
        except APIError as e:
            raise LLMError(f"Anthropic API 错误: {e}")
        except Exception as e:
            raise LLMError(f"Anthropic 流式调用失败: {e}")
