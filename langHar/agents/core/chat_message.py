from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("消息内容不能为空。")
