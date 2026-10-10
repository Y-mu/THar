from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from langHar.agents.agent_service import AgentService
from langHar.agents.core.agent_context import AgentContext, IdentityLevel
from langHar.agents.core.agent_event import AgentEvent
from langHar.agents.core.chat_message import ChatMessage
from langHar.api.modules.conversation.service import ConversationService


class ChatService:
    """协调对话历史、Agent 调用和最终消息持久化。"""

    def __init__(
        self,
        *,
        conversations: ConversationService,
        agent: AgentService,
    ) -> None:
        self._conversations = conversations
        self._agent = agent
        self._conversation_locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def start_stream(
        self,
        *,
        conversation_id: str,
        user_id: int,
        identity_level: IdentityLevel,
        content: str,
    ) -> AsyncIterator[AgentEvent]:
        # 在返回事件流前验证会话归属，让调用方同步处理访问错误。
        await self._conversations.get(conversation_id, user_id)
        return self._stream_message(
            conversation_id=conversation_id,
            user_id=user_id,
            identity_level=identity_level,
            content=content,
        )

    async def _stream_message(
        self,
        *,
        conversation_id: str,
        user_id: int,
        identity_level: IdentityLevel,
        content: str,
    ) -> AsyncIterator[AgentEvent]:
        lock = await self._get_conversation_lock(conversation_id)
        async with lock:
            stored_history = await self._conversations.get_history(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            agent_history = tuple(
                ChatMessage(role=message.role, content=message.content)
                for message in stored_history
            )
            async for event in self._agent.stream(
                content,
                context=AgentContext(
                    session_id=conversation_id,
                    user_id=user_id,
                    identity_level=identity_level,
                    history=agent_history,
                ),
            ):
                if event.type == "final":
                    if not event.content.strip():
                        raise RuntimeError("Agent 未返回最终回答。")
                    await self._conversations.append_exchange(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        user_message=content,
                        assistant_message=event.content,
                    )
                    yield event
                    return

                yield event

            raise RuntimeError("Agent 流未返回 final 事件。")

    async def _get_conversation_lock(
        self,
        conversation_id: str,
    ) -> asyncio.Lock:
        async with self._locks_guard:
            return self._conversation_locks.setdefault(
                conversation_id,
                asyncio.Lock(),
            )
