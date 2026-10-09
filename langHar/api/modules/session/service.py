from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4


class SessionNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class StoredMessage:
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ChatSession:
    session_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    messages: tuple[StoredMessage, ...]


@dataclass(slots=True)
class _SessionRecord:
    session_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[StoredMessage] = field(default_factory=list)
    conversation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionService:
    """按用户隔离的内存会话与消息存储。"""

    def __init__(self) -> None:
        self._sessions: dict[str, _SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, user_id: str) -> ChatSession:
        now = datetime.now(timezone.utc)
        record = _SessionRecord(
            session_id=uuid4().hex,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        async with self._lock:
            self._sessions[record.session_id] = record
        return self._snapshot(record)

    async def list_for_user(self, user_id: str) -> list[ChatSession]:
        async with self._lock:
            records = [
                self._snapshot(record)
                for record in self._sessions.values()
                if record.user_id == user_id
            ]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    async def get(self, session_id: str, user_id: str) -> ChatSession:
        record = await self._get_owned_record(session_id, user_id)
        async with record.conversation_lock:
            return self._snapshot(record)

    async def get_history(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> tuple[StoredMessage, ...]:
        record = await self._get_owned_record(session_id, user_id)
        async with record.conversation_lock:
            return tuple(record.messages)

    async def append_exchange(
        self,
        *,
        session_id: str,
        user_id: str,
        user_message: str,
        assistant_message: str,
    ) -> StoredMessage:
        record = await self._get_owned_record(session_id, user_id)
        async with record.conversation_lock:
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
        session_id: str,
        user_id: str,
    ) -> _SessionRecord:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None or record.user_id != user_id:
                raise SessionNotFoundError(session_id)
            return record

    @staticmethod
    def _snapshot(record: _SessionRecord) -> ChatSession:
        return ChatSession(
            session_id=record.session_id,
            user_id=record.user_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            messages=tuple(record.messages),
        )
