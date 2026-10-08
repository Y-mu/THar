from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Sequence
from types import SimpleNamespace
from unittest.mock import patch

from langHar.agents.agent import AgentService, CLARIFICATION_MESSAGE
from langHar.agents.core.Intention import Intention, IntentMatch
from langHar.agents.core.agent_event import AgentEvent
from langHar.agents.core.chat_message import ChatMessage
from langHar.agents.intent_catalog import INTENT_CATALOG
from langHar.agents.intent_router import IntentRouter
from langHar.agents.langchain_agent import LangChainAgentExecutor
from langHar.bootstrap import create_agent_service
from langHar.config import Settings


class FakeIntention(Intention):
    def __init__(self, intent: str, confidence: float = 0.99) -> None:
        self._match = IntentMatch(
            intent=intent,
            confidence=confidence,
            probabilities={intent: confidence},
            model="fake",
        )

    async def classify(
        self,
        current_message: str,
        context: Sequence[ChatMessage],
    ) -> IntentMatch:
        return self._match


class FakeExecutor:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[tuple[Sequence[ChatMessage], str, str]] = []

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        session_id: str,
        intent: str,
    ) -> AsyncIterator[AgentEvent]:
        self.calls.append((messages, session_id, intent))
        yield AgentEvent(type="token", content=self.answer)
        yield AgentEvent(type="final", content=self.answer)


class FakeCompiledAgent:
    def __init__(self, events: Sequence[dict[str, object]]) -> None:
        self._events = events
        self.input: object = None
        self.config: object = None

    async def astream_events(
        self,
        input: object,
        config: object,
        *,
        version: str,
    ) -> AsyncIterator[dict[str, object]]:
        self.input = input
        self.config = config
        self.version = version
        for event in self._events:
            yield event


def settings() -> Settings:
    return Settings(llm_api_key="llm-test", typesafe_api_key="jev-test")


def create_service(
    intent: str,
    *,
    confidence: float = 0.99,
) -> tuple[AgentService, FakeExecutor]:
    router = IntentRouter(
        FakeIntention(intent, confidence),
        INTENT_CATALOG.keys(),
    )
    executor = FakeExecutor("single-agent-answer")
    return AgentService(router=router, agent=executor), executor


class AgentServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_single_prebuilt_agent_with_routed_intent(self) -> None:
        service, executor = create_service("weather")

        first = await service.handle_message(
            "北京天气",
            session_id="session-1",
            history=(ChatMessage(role="assistant", content="你好"),),
        )
        second = await service.handle_message(
            "上海天气",
            session_id="session-1",
        )

        self.assertEqual(first, "single-agent-answer")
        self.assertEqual(second, "single-agent-answer")
        self.assertEqual(len(executor.calls), 2)
        messages, session_id, intent = executor.calls[0]
        self.assertEqual(session_id, "session-1")
        self.assertEqual(intent, "weather")
        self.assertEqual(messages[-1], ChatMessage(role="user", content="北京天气"))

    async def test_low_confidence_clarifies_without_executing_agent(self) -> None:
        service, executor = create_service("general_chat", confidence=0.1)

        answer = await service.handle_message(
            "随便聊聊",
            session_id="session-2",
        )

        self.assertEqual(answer, CLARIFICATION_MESSAGE)
        self.assertEqual(executor.calls, [])

    async def test_rejects_empty_session_id(self) -> None:
        service, _ = create_service("general_chat")
        with self.assertRaisesRegex(ValueError, "session_id"):
            await service.handle_message("你好", session_id="  ")


class LangChainAgentExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_preserves_stream_and_session_events(self) -> None:
        compiled = FakeCompiledAgent(
            [
                {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": SimpleNamespace(content="北京晴朗")},
                },
                {
                    "event": "on_chain_end",
                    "parent_ids": [],
                    "data": {
                        "output": {
                            "messages": [
                                SimpleNamespace(type="ai", content="北京晴朗")
                            ]
                        }
                    },
                },
            ]
        )
        executor = LangChainAgentExecutor(compiled, INTENT_CATALOG)

        events = [
            event
            async for event in executor.stream(
                [ChatMessage(role="user", content="北京天气")],
                session_id="session-3",
                intent="weather",
            )
        ]

        self.assertEqual(
            [event.type for event in events],
            ["token", "final"],
        )
        self.assertEqual(events[-1].content, "北京晴朗")
        self.assertEqual(
            compiled.config,
            {
                "configurable": {"thread_id": "session-3"},
                "metadata": {"session_id": "session-3", "intent": "weather"},
            },
        )
        self.assertEqual(
            compiled.input["messages"][0],
            {
                "role": "system",
                "content": INTENT_CATALOG["weather"].system_prompt,
            },
        )
        self.assertEqual(
            compiled.input["messages"][1],
            {"role": "user", "content": "北京天气"},
        )


class BootstrapTests(unittest.TestCase):
    def test_creates_exactly_one_toolless_agent_at_startup(self) -> None:
        with (
            patch(
                "langHar.agents.langchain_agent.create_chat_model",
                return_value=object(),
            ),
            patch(
                "langHar.agents.langchain_agent.create_agent",
                side_effect=lambda *args, **kwargs: object(),
            ) as create,
        ):
            service = create_agent_service(settings())

        self.assertIsInstance(service, AgentService)
        create.assert_called_once()
        call = create.call_args
        self.assertEqual(call.kwargs["name"], "intent_agent")
        self.assertEqual(call.kwargs["tools"], [])


if __name__ == "__main__":
    unittest.main()
