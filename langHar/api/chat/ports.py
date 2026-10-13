from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from langHar.core.agent import AgentContext, AgentEvent


class AgentCaller(Protocol):
    """Chat 模块调用 Agent 所需的最小端口。"""

    def stream(
        self,
        message: str,
        *,
        context: AgentContext,
    ) -> AsyncIterator[AgentEvent]: ...
