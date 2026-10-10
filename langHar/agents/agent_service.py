from __future__ import annotations

from collections.abc import AsyncIterator

from langHar.agents.core.agent_context import AgentContext
from langHar.agents.core.agent_event import AgentEvent
from langHar.agents.core.agent_executor import AgentExecutor
from langHar.agents.core.chat_message import ChatMessage
from langHar.agents.intent_recognition import IntentRecognitionService
from langHar.agents.tool_policy import ToolPolicy


CLARIFICATION_MESSAGE = "我还不能确定你的需求，请再具体说明一下。"
TOOL_ACCESS_DENIED_MESSAGE = "当前身份无权使用该能力。"


class AgentService:
    """意图路由和单 Agent 执行服务，不持有会话历史。"""

    def __init__(
        self,
        *,
        intent_recognition: IntentRecognitionService,
        tool_policy: ToolPolicy,
        agent: AgentExecutor,
    ) -> None:
        self._intent_recognition = intent_recognition
        self._tool_policy = tool_policy
        self._agent = agent

    async def invoke(
        self,
        message: str,
        *,
        context: AgentContext,
    ) -> AgentEvent:
        async for event in self.stream(
            message,
            context=context,
        ):
            if event.type == "final":
                return event
        raise RuntimeError("Agent 流未返回 final 事件。")

    async def stream(
        self,
        message: str,
        *,
        context: AgentContext,
    ) -> AsyncIterator[AgentEvent]:
        if not message.strip():
            raise ValueError("message 不能为空。")

        decision = await self._intent_recognition.recognize(
            message,
            context.history,
        )
        if not decision.accepted:
            yield AgentEvent(
                type="final",
                content=CLARIFICATION_MESSAGE,
                reason=decision.reason,
            )
            return

        target = decision.target
        if target is None:
            raise RuntimeError("已拒绝的路由不能执行 Agent。")

        tool_access = self._tool_policy.authorize(
            intent=target,
            identity_level=context.identity_level,
        )
        if not tool_access.accepted:
            yield AgentEvent(
                type="final",
                content=TOOL_ACCESS_DENIED_MESSAGE,
                reason=tool_access.reason,
            )
            return

        messages = (*context.history, ChatMessage(role="user", content=message))
        async for event in self._agent.stream(
            messages,
            context=context,
            intent=target,
            allowed_tools=tool_access.tools,
        ):
            yield event

    async def aclose(self) -> None:
        await self._agent.aclose()
