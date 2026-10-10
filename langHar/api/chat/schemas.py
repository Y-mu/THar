from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ChatEventType = Literal["token", "tool_start", "tool_end", "final", "error"]


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)


class ChatResponse(BaseModel):
    """发送给 Web 客户端的单个对话事件。"""

    type: ChatEventType
    run_id: str
    conversation_id: str
    sequence: int = Field(ge=1)
    content: str
    name: str | None = None
    reason: str | None = None
