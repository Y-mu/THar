from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from langHar.agents.core.agent_event import AgentEvent
from langHar.agents.core.chat_message import ChatMessage


class AgentExecutor(Protocol):
    """启动时创建、请求期间复用的 Agent 执行端口。"""

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        session_id: str,
        intent: str,
    ) -> AsyncIterator[AgentEvent]: ...

