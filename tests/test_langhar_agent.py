from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Sequence
from types import SimpleNamespace
from unittest.mock import patch

from langHar.agents.agent_service import (
    AgentService,
    CLARIFICATION_MESSAGE,
    TOOL_ACCESS_DENIED_MESSAGE,
)
from langHar.agents.intent_recognition import IntentRecognitionService
from langHar.agents.intent_recognition.catalog import INTENT_CATALOG
from langHar.agents.intent_recognition.recognizer import Intention, IntentMatch
from langHar.agents.core.agent_context import AgentContext, IdentityLevel
from langHar.agents.core.agent_event import AgentEvent
from langHar.agents.core.chat_message import ChatMessage
from langHar.agents.langchain_agent import LangChainAgentExecutor
from langHar.agents.agent_factory import create_agent_service
from langHar.agents.tool_policy import ToolPolicy
from langHar.config import Settings
from langHar.tools.base_tools import TOOL_REGISTRY


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
        self.calls: list[
            tuple[Sequence[ChatMessage], AgentContext, str, Sequence[str]]
        ] = []
        self.close_calls = 0

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        context: AgentContext,
        intent: str,
        allowed_tools: Sequence[str],
    ) -> AsyncIterator[AgentEvent]:
        self.calls.append((messages, context, intent, allowed_tools))
        yield AgentEvent(type="token", content=self.answer)
        yield AgentEvent(type="final", content=self.answer)

    async def aclose(self) -> None:
        self.close_calls += 1


class FakeAsyncClient:
    def __init__(self) -> None:
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1


class FakeSyncClient:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class FakeModel:
    def __init__(self) -> None:
        self.root_async_client = FakeAsyncClient()
        self.root_client = FakeSyncClient()


class FakeCompiledAgent:
    def __init__(self, events: Sequence[dict[str, object]]) -> None:
        self._events = events
        self.input: object = None
        self.config: object = None
        self.context: object = None

    async def astream_events(
        self,
        input: object,
        config: object,
        *,
        context: object,
        version: str,
    ) -> AsyncIterator[dict[str, object]]:
        self.input = input
        self.config = config
        self.context = context
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
    intent_recognition = IntentRecognitionService(
        FakeIntention(intent, confidence),
        INTENT_CATALOG.keys(),
    )
    executor = FakeExecutor("single-agent-answer")
    return AgentService(
        intent_recognition=intent_recognition,
        tool_policy=ToolPolicy(INTENT_CATALOG),
        agent=executor,
    ), executor


def agent_context(
    *,
    identity_level: IdentityLevel = IdentityLevel.ADMIN,
    history: tuple[ChatMessage, ...] = (),
) -> AgentContext:
    return AgentContext(
        session_id="session-1",
        user_id=0,
        identity_level=identity_level,
        history=history,
    )


class AgentServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_single_prebuilt_agent_with_routed_intent(self) -> None:
        service, executor = create_service("weather")

        first = await service.invoke(
            "北京天气",
            context=agent_context(
                history=(ChatMessage(role="assistant", content="你好"),),
            ),
        )
        second = await service.invoke(
            "上海天气",
            context=agent_context(),
        )

        self.assertEqual(first.content, "single-agent-answer")
        self.assertEqual(second.content, "single-agent-answer")
        self.assertEqual(len(executor.calls), 2)
        messages, context, intent, allowed_tools = executor.calls[0]
        self.assertEqual(context.session_id, "session-1")
        self.assertEqual(intent, "weather")
        self.assertEqual(allowed_tools, ("get_weather",))
        self.assertEqual(messages[-1], ChatMessage(role="user", content="北京天气"))

    async def test_low_confidence_clarifies_without_executing_agent(self) -> None:
        service, executor = create_service("general_chat", confidence=0.1)

        event = await service.invoke(
            "随便聊聊",
            context=agent_context(),
        )

        self.assertEqual(event.content, CLARIFICATION_MESSAGE)
        self.assertEqual(event.reason, "intent_confidence_below_threshold")
        self.assertEqual(executor.calls, [])

    async def test_context_rejects_empty_session_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "session_id"):
            AgentContext(
                session_id="  ",
                user_id=0,
                identity_level=IdentityLevel.L2,
            )

    async def test_identity_level_denies_unavailable_tool(self) -> None:
        service, executor = create_service("calculator")

        event = await service.invoke(
            "1+1",
            context=agent_context(identity_level=IdentityLevel.L2),
        )

        self.assertEqual(event.content, TOOL_ACCESS_DENIED_MESSAGE)
        self.assertEqual(event.reason, "tool_access_denied")
        self.assertEqual(executor.calls, [])

    async def test_admin_receives_intent_tools(self) -> None:
        service, executor = create_service("calculator")

        await service.invoke("1+1", context=agent_context())

        self.assertEqual(executor.calls[0][3], ("calculate",))

    async def test_closes_agent_resources(self) -> None:
        service, executor = create_service("general_chat")

        await service.aclose()

        self.assertEqual(executor.close_calls, 1)


class LangChainAgentExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_preserves_stream_and_session_events(self) -> None:
        compiled = FakeCompiledAgent(
            [
                {
                    "event": "on_tool_start",
                    "name": "get_weather",
                    "data": {"input": {"location": "北京"}},
                },
                {
                    "event": "on_tool_end",
                    "name": "get_weather",
                    "data": {"output": "北京晴朗"},
                },
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
        model = FakeModel()
        executor = LangChainAgentExecutor(compiled, model, INTENT_CATALOG)

        events = [
            event
            async for event in executor.stream(
                [ChatMessage(role="user", content="北京天气")],
                context=AgentContext(
                    session_id="session-3",
                    user_id=0,
                    identity_level=IdentityLevel.ADMIN,
                ),
                intent="weather",
                allowed_tools=("get_weather",),
            )
        ]

        self.assertEqual(
            [event.type for event in events],
            ["tool_start", "tool_end", "token", "final"],
        )
        self.assertEqual(events[0].name, "get_weather")
        self.assertEqual(events[1].content, "北京晴朗")
        self.assertEqual(events[-1].content, "北京晴朗")
        self.assertEqual(
            compiled.config,
            {
                "configurable": {"thread_id": "session-3"},
                "metadata": {
                    "session_id": "session-3",
                    "user_id": 0,
                    "identity_level": "admin",
                    "intent": "weather",
                },
            },
        )
        self.assertEqual(compiled.context.allowed_tools, {"get_weather"})
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

    async def test_closes_model_clients_once(self) -> None:
        model = FakeModel()
        executor = LangChainAgentExecutor(
            FakeCompiledAgent([]),
            model,
            INTENT_CATALOG,
        )

        await executor.aclose()
        await executor.aclose()

        self.assertEqual(model.root_async_client.close_calls, 1)
        self.assertEqual(model.root_client.close_calls, 1)


class AgentFactoryTests(unittest.TestCase):
    def test_creates_one_agent_with_catalog_tools_at_startup(self) -> None:
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
        self.assertEqual(
            {tool.name for tool in call.kwargs["tools"]},
            {TOOL_REGISTRY["calculate"].name, TOOL_REGISTRY["get_weather"].name},
        )
        self.assertEqual(len(call.kwargs["middleware"]), 2)


if __name__ == "__main__":
    unittest.main()
