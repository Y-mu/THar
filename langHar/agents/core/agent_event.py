from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AgentEventType = Literal["token", "tool_start", "tool_end", "final"]


@dataclass(frozen=True, slots=True)
class AgentEvent:
    """框架无关的 Agent 流式事件。"""

    type: AgentEventType
    content: str
    name: str | None = None
    reason: str | None = None

