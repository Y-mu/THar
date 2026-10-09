from __future__ import annotations

from pydantic import BaseModel, Field

from langHar.api.modules.session.schemas import MessageResponse


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)


class ChatResponse(BaseModel):
    session_id: str
    message: MessageResponse

