from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Protocol

from langHar.core.agent import ChatMessage


@dataclass(frozen=True, slots=True)
class IntentMatch:
    intent: str | None
    confidence: float
    probabilities: dict[str, float]
    model: str


class IntentRecognitionUnavailable(RuntimeError):
    """意图识别服务未能返回可信结果。"""


class IntentRecognizer(Protocol):
    async def classify(
        self,
        current_message: str,
        context: Sequence[ChatMessage],
    ) -> IntentMatch:
        """只识别意图，不决定路由、工具或 Agent。"""


@dataclass(frozen=True, slots=True)
class IntentDecision:
    accepted: bool
    target: str | None
    reason: str
    match: IntentMatch


class IntentRouter:
    """校验识别结果并执行故障关闭策略。"""

    def __init__(
        self,
        recognizer: IntentRecognizer,
        allowed_intents: Collection[str],
        confidence_threshold: float = 0.55,
    ) -> None:
        if not allowed_intents:
            raise ValueError("allowed_intents 不能为空。")
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold 必须在 0 到 1 之间。")
        self._recognizer = recognizer
        self._allowed_intents = frozenset(allowed_intents)
        self._confidence_threshold = confidence_threshold

    async def route(
        self,
        current_message: str,
        context: Sequence[ChatMessage],
    ) -> IntentDecision:
        try:
            match = await self._recognizer.classify(current_message, context)
        except IntentRecognitionUnavailable:
            return self._reject(
                IntentMatch(
                    intent=None,
                    confidence=0.0,
                    probabilities={},
                    model="unavailable",
                ),
                "intention_unavailable",
            )

        if match.intent is None:
            return self._reject(match, "intention_unavailable")
        if match.intent not in self._allowed_intents:
            return self._reject(match, "unknown_intent")
        if match.confidence < self._confidence_threshold:
            return self._reject(match, "intent_confidence_below_threshold")
        return IntentDecision(
            accepted=True,
            target=match.intent,
            reason="intent_accepted",
            match=match,
        )

    @staticmethod
    def _reject(match: IntentMatch, reason: str) -> IntentDecision:
        return IntentDecision(
            accepted=False,
            target=None,
            reason=reason,
            match=match,
        )
