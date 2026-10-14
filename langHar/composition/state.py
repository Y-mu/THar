"""LangGraph state 与输入契约；本地知识库上下文由应用固定提供。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import add_messages

from langHar.core.agent import AgentContext, IdentityLevel


RouteName = Literal["agents", "knowledge", "clarify", "denied"]
DEFAULT_TENANT_ID = "default"
DEFAULT_KNOWLEDGE_BASE_ID = "default"


class AgentGraphInput(TypedDict):
    """公开输入只包含消息，不开放路由、授权、身份或知识库内部状态。"""

    messages: Annotated[list[AnyMessage], add_messages]


class IdentitySnapshot(TypedDict):
    session_id: str
    user_id: int
    identity_level: str
    tenant_id: str
    knowledge_base_id: str


class AgentGraphState(AgentGraphInput):
    identity: NotRequired[IdentitySnapshot | None]
    intent: NotRequired[str | None]
    route: NotRequired[RouteName]
    allowed_tools: NotRequired[list[str]]
    outcome: NotRequired[str]


def reset_turn() -> dict[str, Any]:
    """检查点保留协议历史；每轮重新计算身份、意图和授权。"""
    return {
        "identity": None, "intent": None, "allowed_tools": [], "outcome": "",
    }


def resolve_local_context(config: RunnableConfig | None) -> IdentitySnapshot | None:
    """无登录的单用户开发环境；输入和 configurable 均不能选择知识库身份。"""
    if not isinstance(config, Mapping):
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, Mapping):
        return None
    session_id = configurable.get("thread_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    # 固定本地身份用于现有分块 ACL；不是登录用户或客户端可配置的权限。
    context = AgentContext(session_id.strip(), 0, IdentityLevel.ADMIN)
    return IdentitySnapshot(
        session_id=context.session_id, user_id=context.user_id,
        identity_level=context.identity_level.value, tenant_id=DEFAULT_TENANT_ID,
        knowledge_base_id=DEFAULT_KNOWLEDGE_BASE_ID,
    )
