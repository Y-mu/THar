"""THar Agent 主图：入口节点就是意图门，绕过路由在图结构上不可能发生。"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Overwrite

from langHar.capabilities.tools.policy import ToolPolicy
from langHar.composition.state import (
    AgentGraphInput, AgentGraphState, RouteName, reset_turn, resolve_local_context,
)
from langHar.core.agent import ChatMessage, IdentityLevel
from langHar.orchestration.intent_router import IntentRouter
from langHar.orchestration.messages import (
    CLARIFICATION_MESSAGE,
    TOOL_ACCESS_DENIED_MESSAGE,
)


def build_agent_graph(
    *,
    intent_router: IntentRouter,
    tool_policy: ToolPolicy,
    agents: Any,
    knowledge: Any,
    knowledge_intents: Collection[str],
    name: str = "thar_agent",
) -> Any:
    async def route_intent(
        state: AgentGraphState, config: RunnableConfig,
    ) -> dict[str, Any]:
        # 每轮重新构造本地上下文；没有 thread_id 时不运行模型。
        updates = reset_turn()
        identity = resolve_local_context(config)
        if identity is None:
            return {**updates, "route": "denied", "outcome": "identity_unavailable"}

        messages = state.get("messages") or []
        if not messages or not isinstance(messages[-1], HumanMessage) or not messages[-1].text.strip():
            return {**updates, "route": "clarify", "outcome": "invalid_user_message"}
        # 取消或失败可能留下没有结果的工具调用；协议修复只能由服务端完成。
        repaired = _complete_tool_protocol(messages)
        if len(repaired) != len(messages):
            updates["messages"] = Overwrite(repaired)
        decision = await intent_router.route(messages[-1].text, _history(messages))
        if not decision.accepted or decision.target is None:
            return {**updates, "route": "clarify", "outcome": decision.reason}

        access = tool_policy.authorize(
            intent=decision.target,
            identity_level=IdentityLevel(identity["identity_level"]),
        )
        if not access.accepted:
            return {
                **updates,
                "route": "denied",
                "identity": identity,
                "intent": decision.target,
                "outcome": access.reason,
            }
        return {
            **updates,
            "route": _branch_for(decision.target, knowledge_intents),
            "identity": identity,
            "intent": decision.target,
            "allowed_tools": list(access.tools),
            "outcome": access.reason,
        }

    def clarify(state: AgentGraphState) -> dict[str, Any]:
        return {"messages": [AIMessage(content=CLARIFICATION_MESSAGE)]}

    def denied(state: AgentGraphState) -> dict[str, Any]:
        return {"messages": [AIMessage(content=TOOL_ACCESS_DENIED_MESSAGE)]}

    builder = StateGraph(AgentGraphState, input_schema=AgentGraphInput)
    builder.add_node("route_intent", route_intent)
    builder.add_node("clarify", clarify)
    builder.add_node("denied", denied)
    builder.add_node("agents", agents)
    builder.add_node("knowledge", knowledge)
    builder.add_edge(START, "route_intent")
    builder.add_conditional_edges(
        "route_intent",
        lambda state: state["route"],
        {"clarify": "clarify", "denied": "denied", "agents": "agents", "knowledge": "knowledge"},
    )
    for node in ("clarify", "denied", "agents", "knowledge"):
        builder.add_edge(node, END)
    return builder.compile(name=name)


def _branch_for(intent: str, knowledge_intents: Collection[str]) -> RouteName:
    return "knowledge" if intent in knowledge_intents else "agents"


def _history(messages: Sequence[AnyMessage]) -> tuple[ChatMessage, ...]:
    """只把用户和最终助手消息交给意图识别，工具记录不参与分类。"""
    items: list[ChatMessage] = []
    for message in messages[:-1]:
        if isinstance(message, HumanMessage) and message.text.strip():
            items.append(ChatMessage(role="user", content=message.text))
        elif isinstance(message, AIMessage) and not message.tool_calls and message.text.strip():
            items.append(ChatMessage(role="assistant", content=message.text))
    return tuple(items)



def _complete_tool_protocol(messages: Sequence[AnyMessage]) -> list[AnyMessage]:
    """在下一条非工具消息前补齐被中断的调用，不允许客户端伪造工具结果。"""
    completed: list[AnyMessage] = []
    pending: dict[str, str] = {}
    for message in messages:
        if not isinstance(message, ToolMessage) and pending:
            completed.extend(
                ToolMessage(content="上一轮工具调用未完成。", tool_call_id=call_id, name=name, status="error")
                for call_id, name in pending.items()
            )
            pending.clear()
        completed.append(message)
        if isinstance(message, AIMessage):
            pending.update({call["id"]: call["name"] for call in message.tool_calls})
        elif isinstance(message, ToolMessage):
            pending.pop(message.tool_call_id, None)
    return completed
