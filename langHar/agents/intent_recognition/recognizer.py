from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from langHar.agents.core.chat_message import ChatMessage


@dataclass(frozen=True, slots=True)
class IntentMatch:
    intent: str | None
    confidence: float
    probabilities: dict[str, float]
    model: str


class IntentionRecognitionUnavailable(RuntimeError):
    """意图识别服务未能返回可信结果。"""


class Intention(ABC):
    @abstractmethod
    async def classify(
        self,
        current_message: str,
        context: Sequence[ChatMessage],
    ) -> IntentMatch:
        """只识别意图，不决定路由，也不执行 Agent。"""

