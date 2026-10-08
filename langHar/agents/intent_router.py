from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from langHar.agents.core.Intention import (
    Intention,
    IntentionRecognitionUnavailable,
    IntentMatch,
)
from langHar.agents.core.chat_message import ChatMessage


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    accepted: bool
    target: str | None
    reason: str
    match: IntentMatch


class IntentRouter:
    """根据识别结果执行故障关闭的路由策略。"""

    def __init__(
        self,
        intention: Intention,
        allowed_intents: Collection[str],
        confidence_threshold: float = 0.55,
    ) -> None:
        if not allowed_intents:
            raise ValueError("allowed_intents 不能为空。")
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold 必须在 0 到 1 之间。")
        self._intention = intention
        self._allowed_intents = frozenset(allowed_intents)
        self._confidence_threshold = confidence_threshold

    async def route(
        self,
        current_message: str,
        context: Sequence[ChatMessage],
    ) -> RoutingDecision:
        try:
            match = await self._intention.classify(current_message, context)
        except IntentionRecognitionUnavailable:
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
        return RoutingDecision(
            accepted=True,
            target=match.intent,
            reason="intent_accepted",
            match=match,
        )

    @staticmethod
    def _reject(match: IntentMatch, reason: str) -> RoutingDecision:
        return RoutingDecision(
            accepted=False,
            target=None,
            reason=reason,
            match=match,
        )
