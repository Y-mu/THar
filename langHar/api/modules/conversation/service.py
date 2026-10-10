from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4


class ConversationNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class StoredMessage:
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Conversation:
    conversation_id: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    messages: tuple[StoredMessage, ...]


@dataclass(slots=True)
class _ConversationRecord:
    conversation_id: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    messages: list[StoredMessage] = field(default_factory=list)
    message_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ConversationService:
    """按用户隔离的内存对话与消息存储。"""

    def __init__(self) -> None:
        self._conversations: dict[str, _ConversationRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, user_id: int) -> Conversation:
        now = datetime.now(timezone.utc)
        record = _ConversationRecord(
            conversation_id=uuid4().hex,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        async with self._lock:
            self._conversations[record.conversation_id] = record
        return self._snapshot(record)

    async def list_for_user(self, user_id: int) -> list[Conversation]:
        async with self._lock:
            items = [
                self._snapshot(record)
                for record in self._conversations.values()
                if record.user_id == user_id
            ]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    async def get(
        self,
        conversation_id: str,
        user_id: int,
    ) -> Conversation:
        record = await self._get_owned_record(conversation_id, user_id)
        async with record.message_lock:
            return self._snapshot(record)

    async def get_history(
        self,
        *,
        conversation_id: str,
        user_id: int,
    ) -> tuple[StoredMessage, ...]:
        record = await self._get_owned_record(conversation_id, user_id)
        async with record.message_lock:
            return tuple(record.messages)

    async def append_exchange(
        self,
        *,
        conversation_id: str,
        user_id: int,
        user_message: str,
        assistant_message: str,
    ) -> StoredMessage:
        record = await self._get_owned_record(conversation_id, user_id)
        async with record.message_lock:
            now = datetime.now(timezone.utc)
            record.messages.extend(
                (
                    StoredMessage(role="user", content=user_message, created_at=now),
                    StoredMessage(
                        role="assistant",
                        content=assistant_message,
                        created_at=now,
                    ),
                )
            )
            record.updated_at = now
            return record.messages[-1]

    async def _get_owned_record(
        self,
        conversation_id: str,
        user_id: int,
    ) -> _ConversationRecord:
        async with self._lock:
            record = self._conversations.get(conversation_id)
            if record is None or record.user_id != user_id:
                raise ConversationNotFoundError(conversation_id)
            return record

    @staticmethod
    def _snapshot(record: _ConversationRecord) -> Conversation:
        return Conversation(
            conversation_id=record.conversation_id,
            user_id=record.user_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            messages=tuple(record.messages),
        )
