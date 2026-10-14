"""Framework-independent knowledge response rules; no agent execution or I/O."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from types import MappingProxyType

from langHar.core.knowledge import KnowledgeCatalogResult, KnowledgeToolResult, RetrievalResult


KNOWLEDGE_NO_EVIDENCE_MESSAGE = "知识库中没有足够依据回答该问题。"
KNOWLEDGE_UNAVAILABLE_MESSAGE = "知识库当前不可用，请稍后重试。"
KNOWLEDGE_EMPTY_CATALOG_MESSAGE = "当前知识库没有你可访问的已索引文档。"


@dataclass(frozen=True, slots=True)
class KnowledgeResponseDecision:
    content: str
    accepted: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeResponsePolicy:
    """Pure decisions, evaluated by the knowledge graph before publishing an answer."""

    tool_names = frozenset({"knowledge_search", "knowledge_list_documents"})

    def after_tools(
        self, results: Sequence[KnowledgeToolResult],
    ) -> KnowledgeResponseDecision | None:
        # 1、错误优先，后续成功不能掩盖之前的检索失败。
        if any(
            result.failed or getattr(result.payload, "status", None) == "unavailable"
            for result in results
        ):
            return KnowledgeResponseDecision(
                KNOWLEDGE_UNAVAILABLE_MESSAGE, False, "knowledge_retrieval_unavailable",
            )
        if any(
            result.tool_name not in self.tool_names or result.payload is None
            or (result.tool_name == "knowledge_search" and not isinstance(result.payload, RetrievalResult))
            or (result.tool_name == "knowledge_list_documents" and not isinstance(result.payload, KnowledgeCatalogResult))
            for result in results
        ):
            return self.no_evidence()
        searches = [result.payload for result in results if result.tool_name == "knowledge_search"]
        catalogs = [result.payload for result in results if result.tool_name == "knowledge_list_documents"]
        # 2、正文问答必须有实际引用证据；失败时不能让模型继续编造。
        if any(
            not isinstance(result, RetrievalResult) or result.status != "ok"
            or not result.citations
            or any(
                not re.fullmatch(r"[1-9][0-9]*", citation.citation_id)
                or not citation.source_id.strip() or not citation.document_id.strip()
                or not citation.snippet.strip()
                for citation in result.citations
            )
            for result in searches
        ):
            return self.no_evidence()
        # 3、纯目录查询可直接生成最终回答，无需再次调用模型。
        if catalogs and not searches:
            catalog = catalogs[-1]
            answer = _catalog_answer(catalog) if isinstance(catalog, KnowledgeCatalogResult) else None
            return (
                KnowledgeResponseDecision(answer, True, "knowledge_catalog")
                if answer is not None else self.no_evidence()
            )
        return None

    def after_answer(
        self, content: str, results: Sequence[KnowledgeToolResult],
    ) -> KnowledgeResponseDecision:
        terminal = self.after_tools(results)
        if terminal is not None:
            return terminal
        searches = [result.payload for result in results if isinstance(result.payload, RetrievalResult)]
        if not searches:
            return self.no_evidence()
        citation_ids = {citation.citation_id for result in searches for citation in result.citations}
        used_ids = set(re.findall(r"\[([0-9]+)\]", content))
        if not used_ids or not used_ids.issubset(citation_ids):
            return self.no_evidence("knowledge_answer_missing_citation")
        return KnowledgeResponseDecision(content, True)

    def no_evidence(self, reason: str = "knowledge_no_evidence") -> KnowledgeResponseDecision:
        return KnowledgeResponseDecision(KNOWLEDGE_NO_EVIDENCE_MESSAGE, False, reason)

    def execution_failed(self) -> KnowledgeResponseDecision:
        return KnowledgeResponseDecision(
            KNOWLEDGE_UNAVAILABLE_MESSAGE, False, "knowledge_execution_failed",
        )


def _catalog_answer(result: KnowledgeCatalogResult) -> str | None:
    if result.total < 0 or result.offset < 0:
        return None
    if result.status == "empty":
        return (
            KNOWLEDGE_EMPTY_CATALOG_MESSAGE
            if result.total == 0 and not result.documents and not result.has_more else None
        )
    if result.status != "ok" or result.total <= 0:
        return None
    if not result.documents:
        return (
            f"当前知识库有 {result.total} 份你可访问的已索引文档，此页没有文档，请从第一页查看。"
            if result.offset >= result.total and not result.has_more else None
        )
    if result.offset + len(result.documents) > result.total:
        return None
    if result.has_more != (result.offset + len(result.documents) < result.total):
        return None
    lines = [f"当前知识库有 {result.total} 份你可访问的已索引文档：", ""]
    for index, document in enumerate(result.documents, start=result.offset + 1):
        if not document.source_id.strip() or not document.document_id.strip() or document.chunk_count <= 0:
            return None
        lines.append(
            f"{index}. {_catalog_text(document.source_id)}"
            f"（版本：{_catalog_text('、'.join(document.versions))}；{document.chunk_count} 个可见分块）"
        )
    lines.extend(["", "以上是已索引文档目录，不代表正文内容摘要。你可以继续询问某份文档的内容。"])
    if result.has_more:
        lines.append(f"当前仅显示部分文档，下一页从 offset={result.offset + len(result.documents)} 开始。")
    return "\n".join(lines)


def _catalog_text(value: str) -> str:
    value = escape(" ".join(value.split()))
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value)


RESPONSE_POLICY_REGISTRY = MappingProxyType({"knowledge": KnowledgeResponsePolicy()})
