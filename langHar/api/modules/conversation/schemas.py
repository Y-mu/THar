from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    conversation_id: str
    created_at: datetime
    updated_at: datetime


class ConversationResponse(ConversationSummaryResponse):
    messages: list[MessageResponse]
