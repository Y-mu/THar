from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from langHar.agents.core.agent_event import AgentEvent
from langHar.agents.core.agent_executor import AgentExecutor
from langHar.agents.core.chat_message import ChatMessage
from langHar.agents.intent_router import IntentRouter


CLARIFICATION_MESSAGE = "我还不能确定你的需求，请再具体说明一下。"


class AgentService:
    """意图路由和单 Agent 执行服务，不持有会话历史。"""

    def __init__(
        self,
        *,
        router: IntentRouter,
        agent: AgentExecutor,
    ) -> None:
        self._router = router
        self._agent = agent

    async def handle_message(
        self,
        message: str,
        *,
        session_id: str,
        history: Sequence[ChatMessage] = (),
    ) -> str:
        final_answer = ""
        async for event in self.stream_message(
            message,
            session_id=session_id,
            history=history,
        ):
            if event.type == "final":
                final_answer = event.content
        return final_answer

    async def stream_message(
        self,
        message: str,
        *,
        session_id: str,
        history: Sequence[ChatMessage] = (),
    ) -> AsyncIterator[AgentEvent]:
        if not session_id.strip():
            raise ValueError("session_id 不能为空。")
        if not message.strip():
            raise ValueError("message 不能为空。")

        decision = await self._router.route(message, history)
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

        messages = (*history, ChatMessage(role="user", content=message))
        async for event in self._agent.stream(
            messages,
            session_id=session_id,
            intent=target,
        ):
            yield event

    async def aclose(self) -> None:
        await self._agent.aclose()

