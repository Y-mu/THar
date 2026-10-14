"""MVP 知识库节点：本轮工具执行、成文与审计在一次状态提交中完成。"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import TAG_NOSTREAM

from langHar.capabilities.knowledge.policy import (
    KNOWLEDGE_NO_EVIDENCE_MESSAGE, KNOWLEDGE_UNAVAILABLE_MESSAGE, KnowledgeResponsePolicy,
)
from langHar.capabilities.tools.registry import TOOL_REGISTRY
from langHar.composition.state import AgentGraphState, resolve_local_context
from langHar.core.agent import AgentContext, IdentityLevel
from langHar.core.knowledge import (
    Citation, IndexedDocument, KnowledgeCatalogQuery, KnowledgeCatalogResult,
    KnowledgeToolResult, RetrievalQuery, RetrievalResult,
)

logger = logging.getLogger(__name__)
SEARCH_TOOL = "knowledge_search"
CATALOG_TOOL = "knowledge_list_documents"


def build_knowledge_node(
    *,
    model: BaseChatModel,
    search: Callable[[RetrievalQuery], Awaitable[RetrievalResult]],
    list_documents: Callable[[KnowledgeCatalogQuery], Awaitable[KnowledgeCatalogResult]],
    policy: KnowledgeResponsePolicy,
    plan_prompts: Mapping[str, str],
    compose_prompt: str,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    tools = {
        SEARCH_TOOL: TOOL_REGISTRY[SEARCH_TOOL](search),
        CATALOG_TOOL: TOOL_REGISTRY[CATALOG_TOOL](list_documents),
    }

    async def knowledge(state: AgentGraphState, config: RunnableConfig) -> dict[str, Any]:
        protocol: list = []

        def finish(content: str, outcome: str) -> dict[str, Any]:
            return {"messages": [*protocol, AIMessage(content=content)], "outcome": outcome}

        identity = resolve_local_context(config)
        if identity is None:
            return finish(KNOWLEDGE_NO_EVIDENCE_MESSAGE, "knowledge_tool_denied")
        allowed = set(state.get("allowed_tools") or ())
        try:
            planner = model.bind_tools([tool for name, tool in tools.items() if name in allowed])
            response = await planner.ainvoke(
                [SystemMessage(content=plan_prompts[str(state["intent"])]), *state["messages"]],
                config={"tags": [TAG_NOSTREAM]},
            )
        except Exception:
            logger.exception("知识库计划阶段失败")
            return finish(KNOWLEDGE_UNAVAILABLE_MESSAGE, "knowledge_plan_failed")

        calls = list(getattr(response, "tool_calls", ()) or ())
        if len(calls) != 1 or calls[0]["name"] not in tools or calls[0]["name"] not in allowed:
            return finish(KNOWLEDGE_NO_EVIDENCE_MESSAGE, "knowledge_tool_denied")
        call = calls[0]
        tool_name = call["name"]
        args = call.get("args") or {}
        if tool_name == SEARCH_TOOL:
            tool_args = {"query": str(args.get("query", "")).strip()}
        else:
            limit, offset = args.get("limit", 50), args.get("offset", 0)
            tool_args = {
                "limit": min(max(limit, 1), 100) if type(limit) is int else 50,
                "offset": max(offset, 0) if type(offset) is int else 0,
            }
        # 工具调用只保留公开参数，模型指定的身份、ACL 或 runtime 一律丢弃。
        protocol.append(AIMessage(content="", tool_calls=[{**call, "args": tool_args}]))
        context = AgentContext(
            session_id=identity["session_id"], user_id=identity["user_id"],
            identity_level=IdentityLevel(identity["identity_level"]),
            tenant_id=identity["tenant_id"], knowledge_base_id=identity["knowledge_base_id"],
        )
        runtime = ToolRuntime(
            state=state, context=context, config=config, stream_writer=lambda _: None,
            tool_call_id=call["id"], store=None,
        )
        if tool_name == SEARCH_TOOL and not tool_args["query"]:
            protocol.append(ToolMessage(
                content=KNOWLEDGE_NO_EVIDENCE_MESSAGE, name=tool_name,
                tool_call_id=call["id"], status="error",
            ))
            return finish(KNOWLEDGE_NO_EVIDENCE_MESSAGE, "knowledge_empty_query")
        try:
            content = await tools[tool_name].ainvoke({**tool_args, "runtime": runtime}, config=config)
            result = _decode_result(tool_name, json.loads(content))
            protocol.append(ToolMessage(content=content, name=tool_name, tool_call_id=call["id"]))
        except Exception:
            logger.exception("知识库检索失败")
            protocol.append(ToolMessage(
                content=KNOWLEDGE_UNAVAILABLE_MESSAGE, name=tool_name,
                tool_call_id=call["id"], status="error",
            ))
            return finish(KNOWLEDGE_UNAVAILABLE_MESSAGE, "knowledge_retrieval_failed")

        decision = policy.after_tools([result])
        if decision is not None:
            return finish(decision.content, decision.reason or "knowledge_terminal")
        evidence = "\n\n".join(
            f"[{item.citation_id}] 来源：{item.source_id}"
            + (f"（第 {item.page} 页）" if item.page is not None else "")
            + f"\n{item.snippet}"
            for item in result.payload.citations
        )
        try:
            response = await model.ainvoke(
                [SystemMessage(content=compose_prompt.format(evidence=evidence)),
                 next(message for message in reversed(state["messages"]) if isinstance(message, HumanMessage))],
                config={"tags": [TAG_NOSTREAM]},
            )
        except Exception:
            logger.exception("知识库成文失败")
            return finish(KNOWLEDGE_UNAVAILABLE_MESSAGE, "knowledge_compose_failed")
        # 草稿和证据不作为独立 state 字段保存；审计之后才提交助手消息。
        decision = policy.after_answer(response.text, [result])
        return finish(decision.content, decision.reason or "knowledge_accepted")

    return knowledge


def _decode_result(tool_name: str, payload: dict[str, Any]) -> KnowledgeToolResult:
    if tool_name == SEARCH_TOOL:
        result = RetrievalResult(
            status=payload["status"],
            citations=tuple(Citation(
                citation_id=row["id"], source_id=row["source_id"], document_id=row["document_id"],
                snippet=row["snippet"], page=row.get("page"),
            ) for row in payload.get("citations", ())),
        )
    else:
        result = KnowledgeCatalogResult(
            status=payload["status"], total=payload.get("total", 0),
            offset=payload.get("offset", 0), has_more=payload.get("has_more", False),
            documents=tuple(IndexedDocument(**row) for row in payload.get("documents", ())),
        )
    return KnowledgeToolResult(tool_name, result)
