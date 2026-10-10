from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRequest,
    ToolCallRequest,
    wrap_model_call,
    wrap_tool_call,
)
from langchain_openai import ChatOpenAI

from langHar.agents.core.agent_context import AgentContext
from langHar.agents.core.agent_event import AgentEvent
from langHar.agents.core.agent_executor import AgentExecutor
from langHar.agents.core.chat_message import ChatMessage
from langHar.agents.intent_recognition.catalog import IntentSpec
from langHar.config import Settings
from langHar.tools.base_tools import TOOL_REGISTRY


@dataclass(frozen=True, slots=True)
class _LangChainRunContext:
    agent: AgentContext
    allowed_tools: frozenset[str]


@wrap_model_call
async def _filter_model_tools(request: ModelRequest, handler: Any) -> Any:
    run_context = request.runtime.context
    allowed = run_context.allowed_tools
    tools = [tool for tool in request.tools if _tool_name(tool) in allowed]
    return await handler(request.override(tools=tools))


@wrap_tool_call
async def _guard_tool_call(request: ToolCallRequest, handler: Any) -> Any:
    run_context = request.runtime.context
    tool_name = str(request.tool_call.get("name", ""))
    if tool_name not in run_context.allowed_tools:
        raise PermissionError(f"工具 {tool_name!r} 未获得本次调用授权。")
    return await handler(request)


class LangChainAgentExecutor(AgentExecutor):
    """最小化的单 Agent 适配器。"""

    def __init__(
        self,
        agent: Any,
        model: ChatOpenAI,
        catalog: Mapping[str, IntentSpec],
    ) -> None:
        self._agent = agent
        self._model = model
        self._catalog = catalog
        self._closed = False

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        context: AgentContext,
        intent: str,
        allowed_tools: Sequence[str],
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
            "configurable": {"thread_id": context.session_id},
            "metadata": {
                "session_id": context.session_id,
                "user_id": context.user_id,
                "identity_level": context.identity_level.value,
                "intent": intent,
            },
        }
        run_context = _LangChainRunContext(
            agent=context,
            allowed_tools=frozenset(allowed_tools),
        )
        streamed_parts: list[str] = []

        async for event in self._agent.astream_events(
            {"messages": input_messages},
            config=config,
            context=run_context,
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
            elif event_type == "on_tool_start":
                yield AgentEvent(
                    type="tool_start",
                    content="",
                    name=str(event.get("name", "")) or None,
                )
            elif event_type == "on_tool_end":
                output = data.get("output", "")
                yield AgentEvent(
                    type="tool_end",
                    content=_content_to_text(getattr(output, "content", output)),
                    name=str(event.get("name", "")) or None,
                )

        yield AgentEvent(type="final", content="".join(streamed_parts))

    async def aclose(self) -> None:
        """关闭 ChatOpenAI 创建的异步和同步 HTTP 客户端。"""
        if self._closed:
            return
        self._closed = True
        try:
            await self._model.root_async_client.close()
        finally:
            self._model.root_client.close()


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

    configured_tool_names = {
        permission.name
        for spec in catalog.values()
        for permission in spec.tools
    }
    missing_tools = configured_tool_names.difference(TOOL_REGISTRY)
    if missing_tools:
        raise ValueError(
            f"INTENT_CATALOG 引用了未注册工具：{', '.join(sorted(missing_tools))}。"
        )

    model = create_chat_model(settings)
    compiled_agent = create_agent(
        model,
        tools=[TOOL_REGISTRY[name] for name in sorted(configured_tool_names)],
        middleware=[_filter_model_tools, _guard_tool_call],
        context_schema=_LangChainRunContext,
        name="intent_agent",
    )
    return LangChainAgentExecutor(compiled_agent, model, catalog)


def _tool_name(tool: Any) -> str:
    if isinstance(tool, Mapping):
        name = tool.get("name")
        if isinstance(name, str):
            return name
        function = tool.get("function")
        if isinstance(function, Mapping) and isinstance(function.get("name"), str):
            return function["name"]
        return ""
    return str(getattr(tool, "name", ""))


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
