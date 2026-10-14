"""Retrieval policy, ACL filtering and citation assembly."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from langHar.core.knowledge import (
    Citation, IndexedDocument, KnowledgeCatalogQuery, KnowledgeCatalogResult,
    RetrievalQuery, RetrievalResult, VectorMatch,
)
from langHar.orchestration.retrieval_ports import KnowledgeCatalogStore, KnowledgeVectorStore


logger = logging.getLogger(__name__)


class KnowledgeCatalogService:
    """Filter metadata by trusted scope/ACL before deduplication and pagination."""

    def __init__(self, store: KnowledgeCatalogStore) -> None:
        self._store = store

    async def list_documents(self, request: KnowledgeCatalogQuery) -> KnowledgeCatalogResult:
        try:
            metadata_rows = await self._store.list_metadata(request)
        except Exception as exc:
            logger.exception("知识库目录读取失败")
            return KnowledgeCatalogResult(
                status="unavailable", reason=f"catalog_unavailable:{type(exc).__name__}",
            )

        # 1、先执行租户、知识库和分块 ACL 校验，隐藏文档不参与计数。
        grouped: dict[tuple[str, str], list[Mapping[str, object]]] = {}
        for metadata in metadata_rows:
            if not _scope_matches(metadata, request):
                continue
            if not _acl_allows(metadata, request.identity_level.value):
                continue
            document_id = metadata.get("document_id")
            source_id = metadata.get("source_id")
            if not isinstance(document_id, str) or not document_id.strip():
                continue
            if not isinstance(source_id, str) or not source_id.strip():
                continue
            grouped.setdefault((document_id, source_id), []).append(metadata)

        # 2、按来源聚合，不能把向量分块数量误认为文档数量。
        documents = sorted(
            (
                IndexedDocument(
                    document_id=document_id,
                    source_id=source_id,
                    versions=tuple(sorted({str(row.get("version", "unknown")) for row in rows})),
                    chunk_count=len(rows),
                )
                for (document_id, source_id), rows in grouped.items()
            ),
            key=lambda document: (document.source_id, document.document_id),
        )
        # 3、仅在权限过滤后分页，total 始终表示当前用户可见的文档数。
        end = request.offset + request.limit
        return KnowledgeCatalogResult(
            status="ok" if documents else "empty",
            documents=tuple(documents[request.offset:end]),
            total=len(documents), offset=request.offset, has_more=end < len(documents),
        )


class RetrievalService:
    """Owns the safe, evidence-only retrieval use case."""

    def __init__(self, store: KnowledgeVectorStore) -> None:
        self._store = store

    async def search(self, request: RetrievalQuery) -> RetrievalResult:
        try:
            matches = await self._store.search(request)
        except Exception as exc:  # fail closed for unavailable vector stores
            logger.exception("知识库向量检索失败")
            return RetrievalResult(
                status="unavailable",
                reason=f"vector_store_unavailable:{type(exc).__name__}",
            )

        accepted: list[VectorMatch] = []
        for match in matches:
            if match.score < request.min_score:
                continue
            metadata = match.chunk.metadata
            if not _scope_matches(metadata, request):
                continue
            if not _acl_allows(metadata, request.identity_level.value):
                continue
            accepted.append(match)
            if len(accepted) >= request.top_k:
                break

        if not accepted:
            return RetrievalResult(status="no_evidence", reason="no_authorized_evidence")

        citations = tuple(
            Citation(
                citation_id=str(index),
                source_id=str(match.chunk.metadata.get("source_id", "unknown")),
                document_id=str(match.chunk.metadata.get("document_id", "unknown")),
                snippet=match.chunk.content,
                page=_page_number(match.chunk.metadata.get("page")),
            )
            for index, match in enumerate(accepted, start=1)
        )
        return RetrievalResult(
            status="ok",
            chunks=tuple(match.chunk for match in accepted),
            citations=citations,
        )


def _scope_matches(
    metadata: Mapping[str, object], request: RetrievalQuery | KnowledgeCatalogQuery,
) -> bool:
    return (
        str(metadata.get("tenant_id", "")) == request.tenant_id
        and str(metadata.get("knowledge_base_id", ""))
        == request.knowledge_base_id
    )


def _acl_allows(metadata: Mapping[str, object], identity_level: str) -> bool:
    raw_acl = metadata.get("acl")
    if raw_acl is None:
        return False
    if isinstance(raw_acl, (list, tuple, frozenset, set)):
        values = {str(value).strip() for value in raw_acl}
    else:
        values = {value.strip() for value in str(raw_acl).split(",")}
    return identity_level in values


def _page_number(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
