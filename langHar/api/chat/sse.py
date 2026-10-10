"""Agent 应用事件到 SSE 响应的表示层映射。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import uuid4

from sse_starlette import EventSourceResponse, ServerSentEvent

from langHar.api.chat.schemas import ChatResponse
from langHar.core.agent import AgentEvent


logger = logging.getLogger(__name__)


def create_chat_stream_response(
    events: AsyncIterator[AgentEvent],
    *,
    conversation_id: str,
) -> EventSourceResponse:
    return EventSourceResponse(
        _encode_event_stream(events, conversation_id=conversation_id),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _encode_event_stream(
    events: AsyncIterator[AgentEvent],
    *,
    conversation_id: str,
) -> AsyncIterator[ServerSentEvent]:
    run_id = uuid4().hex
    sequence = 0

    try:
        async for event in events:
            sequence += 1
            yield _encode_response(
                ChatResponse(
                    type=event.type,
                    run_id=run_id,
                    conversation_id=conversation_id,
                    sequence=sequence,
                    content=event.content,
                    name=event.name,
                    reason=event.reason,
                )
            )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            "对话事件流异常",
            extra={"run_id": run_id, "conversation_id": conversation_id},
        )
        sequence += 1
        yield _encode_response(
            ChatResponse(
                type="error",
                run_id=run_id,
                conversation_id=conversation_id,
                sequence=sequence,
                content="事件流异常中断，请稍后重试。",
                reason="stream_error",
            )
        )


def _encode_response(response: ChatResponse) -> ServerSentEvent:
    return ServerSentEvent(
        id=f"{response.run_id}:{response.sequence}",
        event=response.type,
        data=response.model_dump_json(exclude_none=True),
    )
