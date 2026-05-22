"""LLM Gateway endpoints — chat completion with SSE streaming support."""
import json
import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..schemas.config import ChatCompletionRequest
from ..ai.gateway import LLMGateway
from ..core.exceptions import LLMError
from ..core.response import ApiResponse

router = APIRouter(tags=["llm"])


async def _sse_stream(
    generator: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """Wrap token generator into SSE format."""
    full_text = ""
    try:
        async for chunk in generator:
            full_text += chunk
            data = json.dumps({"type": "token", "content": chunk}, ensure_ascii=False, separators=(",", ":"))
            yield f"data: {data}\n\n"
        # Send completion event with full text
        done_data = json.dumps(
            {"type": "done", "full_text": full_text, "usage": None},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        yield f"data: {done_data}\n\n"
        yield "data: [DONE]\n\n"
    except LLMError as e:
        error_data = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False, separators=(",", ":"))
        yield f"data: {error_data}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        error_data = json.dumps(
            {"type": "error", "message": f"服务器错误: {e}"},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        yield f"data: {error_data}\n\n"
        yield "data: [DONE]\n\n"


@router.post("/chat/completion")
async def chat_completion(payload: ChatCompletionRequest):
    """Non-streaming chat completion through LLM Gateway."""
    try:
        result = await LLMGateway.chat_completion(
            messages=payload.messages,
            model=payload.model,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
        return ApiResponse.success(data=result)
    except LLMError as e:
        # Re-raise as API error with proper code
        raise LLMError(str(e))
    except Exception as e:
        raise LLMError(f"LLM调用失败: {e}")


@router.post("/chat/completion/stream")
async def stream_chat_completion(payload: ChatCompletionRequest):
    """Streaming chat completion via Server-Sent Events (SSE).
    
    SSE format:
        data: {"type":"token","content":"生成的"}
        data: {"type":"token","content":"文本"}
        data: {"type":"done","full_text":"完整文本","usage":null}
        data: [DONE]
    """
    async def event_generator():
        gen = LLMGateway.stream_chat_completion(
            messages=payload.messages,
            model=payload.model,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
        async for event in _sse_stream(gen):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
