from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class IdentityLevel(StrEnum):
    ADMIN = "admin"
    L0 = "l0"
    L1 = "l1"
    L2 = "l2"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("消息内容不能为空。")


@dataclass(frozen=True, slots=True)
class AgentContext:
    """一次 Agent 调用独有的可信运行上下文。"""

    session_id: str
    user_id: int
    identity_level: IdentityLevel
    tenant_id: str = "default"
    knowledge_base_id: str = "default"

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id 不能为空。")
        if self.user_id < 0:
            raise ValueError("user_id 不能小于 0。")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id 不能为空。")
        if not self.knowledge_base_id.strip():
            raise ValueError("knowledge_base_id 不能为空。")
