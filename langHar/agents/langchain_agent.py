from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from langHar.agents.core.agent_event import AgentEvent
from langHar.agents.core.agent_executor import AgentExecutor
from langHar.agents.core.chat_message import ChatMessage
from langHar.agents.intent_catalog import IntentSpec
from langHar.config import Settings


class LangChainAgentExecutor(AgentExecutor):
    """最小化的单 Agent 适配器。"""

    def __init__(
        self,
        agent: Any,
        catalog: Mapping[str, IntentSpec],
    ) -> None:
        self._agent = agent
        self._catalog = catalog

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        session_id: str,
        intent: str,
    ) -> AsyncIterator[AgentEvent]:
        spec = self._catalog[intent]
        input_messages = [
            {"role": "system", "content": spec.system_prompt},
        ]
        input_messages.extend(
            {"role": message.role, "content": message.content}
            for message in messages
        )
        config = {
            "configurable": {"thread_id": session_id},
            "metadata": {"session_id": session_id, "intent": intent},
        }
        streamed_parts: list[str] = []

        async for event in self._agent.astream_events(
            {"messages": input_messages},
            config=config,
            version="v2",
        ):
            event_type = event.get("event")
            data = event.get("data", {})
            if event_type == "on_chat_model_stream":
                chunk: Any = data.get("chunk")
                content = _content_to_text(getattr(chunk, "content", ""))
                if content:
                    streamed_parts.append(content)
                    yield AgentEvent(type="token", content=content)

        yield AgentEvent(type="final", content="".join(streamed_parts))


def create_chat_model(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def create_agent_executor(
    settings: Settings,
    catalog: Mapping[str, IntentSpec],
) -> AgentExecutor:

    if not catalog:
        raise ValueError("catalog 不能为空。")

    model = create_chat_model(settings)
    compiled_agent = create_agent(
        model,
        tools=[],
        name="intent_agent",
    )
    return LangChainAgentExecutor(compiled_agent, catalog)


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, Sequence) or isinstance(content, (bytes, bytearray)):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, Mapping):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)
