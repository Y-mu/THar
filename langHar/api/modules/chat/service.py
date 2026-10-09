from __future__ import annotations

import asyncio

from langHar.agents.agent_service import AgentService
from langHar.agents.core.chat_message import ChatMessage
from langHar.api.modules.session.service import SessionService, StoredMessage


class ChatService:
    """协调对话历史、Agent 调用和最终消息持久化。"""

    def __init__(
        self,
        *,
        sessions: SessionService,
        agent: AgentService,
    ) -> None:
        self._sessions = sessions
        self._agent = agent
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def send_message(
        self,
        *,
        session_id: str,
        user_id: str,
        content: str,
    ) -> StoredMessage:
        lock = await self._get_session_lock(session_id)
        async with lock:
            stored_history = await self._sessions.get_history(
                session_id=session_id,
                user_id=user_id,
            )
            agent_history = tuple(
                ChatMessage(role=message.role, content=message.content)
                for message in stored_history
            )
            answer = await self._agent.handle_message(
                content,
                session_id=session_id,
                history=agent_history,
            )
            if not answer.strip():
                raise RuntimeError("Agent 未返回最终回答。")
            return await self._sessions.append_exchange(
                session_id=session_id,
                user_id=user_id,
                user_message=content,
                assistant_message=answer,
            )

    async def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        async with self._locks_guard:
            return self._session_locks.setdefault(session_id, asyncio.Lock())
