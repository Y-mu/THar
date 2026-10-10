from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from langHar.agents.core.agent_context import AgentContext
from langHar.agents.core.agent_event import AgentEvent
from langHar.agents.core.chat_message import ChatMessage


class AgentExecutor(Protocol):
    """启动时创建、请求期间复用的 Agent 执行端口。"""

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        context: AgentContext,
        intent: str,
        allowed_tools: Sequence[str],
    ) -> AsyncIterator[AgentEvent]: ...

    async def aclose(self) -> None: ...
