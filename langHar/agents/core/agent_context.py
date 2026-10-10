from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from langHar.agents.core.chat_message import ChatMessage


class IdentityLevel(StrEnum):
    ADMIN = "admin"
    L0 = "l0"
    L1 = "l1"
    L2 = "l2"


@dataclass(frozen=True, slots=True)
class AgentContext:
    """一次 Agent 调用独有的可信运行上下文。"""

    session_id: str
    user_id: int
    identity_level: IdentityLevel
    history: tuple[ChatMessage, ...] = ()

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id 不能为空。")
        if self.user_id < 0:
            raise ValueError("user_id 不能小于 0。")
