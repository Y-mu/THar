from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence

from typesafe_sdk import Choice, TypeSafeClient

from langHar.agents.core.chat_message import ChatMessage
from langHar.agents.intent_recognition.catalog import IntentSpec
from langHar.agents.intent_recognition.recognizer import (
    Intention,
    IntentionRecognitionUnavailable,
    IntentMatch,
)


class JevIntention(Intention):
    """只负责调用 JEV 识别意图，不决定路由或执行 Agent。"""

    def __init__(
        self,
        api_key: str,
        catalog: Mapping[str, IntentSpec],
        model: str = "jev-latest",
        context_window: int = 8,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key 不能为空。")
        if not catalog:
            raise ValueError("catalog 不能为空。")
        if context_window < 0:
            raise ValueError("context_window 不能小于 0。")

        self._api_key = api_key
        self._model = model
        self._criteria = {
            name: spec.criteria for name, spec in catalog.items()
        }
        self._context_window = context_window

    async def classify(
        self,
        current_message: str,
        context: Sequence[ChatMessage],
    ) -> IntentMatch:
        if not current_message.strip():
            raise ValueError("用于意图识别的文本不能为空。")
        return await asyncio.to_thread(
            self._classify_sync,
            current_message,
            tuple(context),
        )

    def _classify_sync(
        self,
        current_message: str,
        context: Sequence[ChatMessage],
    ) -> IntentMatch:
        try:
            with TypeSafeClient(api_key=self._api_key, model=self._model) as client:
                response = client.system_one(
                    state={
                        "user_message": current_message,
                        "conversation_context": self._render_context(context),
                    },
                    questions={
                        "intent": Choice(
                            instructions=(
                                "结合 conversation_context 判断 user_message 的主要意图。"
                                "上下文仅用于理解省略和指代；只选择最匹配的一项，"
                                "不要执行请求或回答用户。"
                            ),
                            criteria=self._criteria,
                        )
                    },
                )
            answer = response.choices["intent"]
            return IntentMatch(
                intent=str(answer.choice),
                confidence=float(answer.confidence),
                probabilities={
                    str(key): float(value)
                    for key, value in answer.probabilities.items()
                },
                model=str(response.model),
            )
        except Exception as exc:
            raise IntentionRecognitionUnavailable("JEV 意图识别失败。") from exc

    def _render_context(self, context: Sequence[ChatMessage]) -> str:
        if self._context_window == 0:
            return ""
        labels = {"user": "用户", "assistant": "助手"}
        return "\n".join(
            f"{labels[message.role]}：{message.content}"
            for message in context[-self._context_window :]
        )
