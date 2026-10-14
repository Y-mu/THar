from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Any

from langchain.tools import ToolRuntime, tool

from langHar.core.agent import AgentContext
from langHar.core.knowledge import (
    KnowledgeCatalogQuery, KnowledgeCatalogResult, RetrievalQuery, RetrievalResult,
)


RetrievalCallable = Callable[[RetrievalQuery], Awaitable[RetrievalResult]]
CatalogCallable = Callable[[KnowledgeCatalogQuery], Awaitable[KnowledgeCatalogResult]]


def create_knowledge_list_tool(list_documents: CatalogCallable) -> Any:
    """Create an ACL-scoped catalog tool; the model cannot choose the scope."""

    @tool("knowledge_list_documents")
    async def knowledge_list_documents(
        runtime: ToolRuntime[Any], limit: int = 50, offset: int = 0,
    ) -> str:
        """List indexed documents visible to the current user, without semantic search.

        Use for '知识库里有什么', '有哪些文档', or browsing the knowledge catalog.
        Returns document sources, indexed versions and visible chunk counts, not content.
        For questions about document contents use knowledge_search instead.

        Args:
            limit: Documents per page, from 1 to 100 (default 50).
            offset: Number of visible documents to skip (default 0).
        """
        context = _agent_context(runtime)
        result = await list_documents(KnowledgeCatalogQuery(
            tenant_id=context.tenant_id, knowledge_base_id=context.knowledge_base_id,
            user_id=context.user_id, identity_level=context.identity_level,
            limit=limit, offset=offset,
        ))
        return json.dumps(asdict(result), ensure_ascii=False)

    return knowledge_list_documents


def create_knowledge_search_tool(search: RetrievalCallable) -> Any:
    """Create a tool whose scope comes only from the trusted runtime context."""

    @tool("knowledge_search")
    async def knowledge_search(query: str, runtime: ToolRuntime[Any]) -> str:
        """Search authorized document contents for a specific question with citations.

        For '知识库里有什么' or a document inventory use knowledge_list_documents,
        not this similarity search: top-k chunks do not represent the full catalog.
        """

        # ToolRuntime 的默认上下文类型为 None；显式允许适配器包装的上下文，
        # 再由 _agent_context 校验可信 AgentContext，避免序列化类型不匹配。
        if not query.strip():
            raise ValueError("检索 query 不能为空。")
        context = _agent_context(runtime)
        result = await search(
            RetrievalQuery(
                query=query,
                tenant_id=context.tenant_id,
                knowledge_base_id=context.knowledge_base_id,
                user_id=context.user_id,
                identity_level=context.identity_level,
            )
        )
        return _serialize_result(result)

    return knowledge_search


def _agent_context(runtime: ToolRuntime[Any]) -> AgentContext:
    context: Any = runtime.context
    context = getattr(context, "agent", context)
    if not isinstance(context, AgentContext):
        raise PermissionError("缺少可信 AgentContext，拒绝知识库检索。")
    return context


def _serialize_result(result: RetrievalResult) -> str:
    return json.dumps(
        {
            "status": result.status,
            "reason": result.reason,
            "citations": [
                {
                    "id": citation.citation_id,
                    "source_id": citation.source_id,
                    "document_id": citation.document_id,
                    "page": citation.page,
                    "snippet": citation.snippet,
                }
                for citation in result.citations
            ],
        },
        ensure_ascii=False,
    )
