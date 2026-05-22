"""Base adapter interface for all LLM providers."""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class BaseAdapter(ABC):
    """Abstract base class for LLM provider adapters."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_body: Optional[dict] = None,
    ) -> dict:
        """Non-streaming chat completion.

        Returns:
            {
                "content": str,
                "model": str,
                "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
            }
        """
        ...

    @abstractmethod
    async def stream_chat_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_body: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion — yields token chunks."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier string."""
        ...
