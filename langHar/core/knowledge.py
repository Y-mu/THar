"""Framework-independent contracts for the knowledge retrieval pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from langHar.core.agent import IdentityLevel


SUPPORTED_DOCUMENT_SUFFIXES = frozenset({".md", ".markdown", ".txt"})


RetrievalStatus = Literal["ok", "no_evidence", "unavailable"]


@dataclass(frozen=True, slots=True)
class KnowledgeCatalogQuery:
    """Trusted scope and pagination for browsing indexed document metadata."""

    tenant_id: str
    knowledge_base_id: str
    user_id: int
    identity_level: IdentityLevel
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.knowledge_base_id.strip():
            raise ValueError("知识库范围不能为空。")
        if self.user_id < 0:
            raise ValueError("user_id 不能小于 0。")
        if type(self.limit) is not int or type(self.offset) is not int:
            raise ValueError("limit 和 offset 必须是整数。")
        if not 1 <= self.limit <= 100 or self.offset < 0:
            raise ValueError("limit 必须在 1 到 100 之间，offset 不能小于 0。")


@dataclass(frozen=True, slots=True)
class IndexedDocument:
    document_id: str
    source_id: str
    versions: tuple[str, ...]
    chunk_count: int


@dataclass(frozen=True, slots=True)
class KnowledgeCatalogResult:
    status: Literal["ok", "empty", "unavailable"]
    documents: tuple[IndexedDocument, ...] = ()
    total: int = 0
    offset: int = 0
    has_more: bool = False
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """A chunk that can be indexed without exposing LangChain types."""

    chunk_id: str
    content: str
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.chunk_id.strip():
            raise ValueError("chunk_id 不能为空。")
        if not self.content.strip():
            raise ValueError("chunk content 不能为空。")


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """A trusted retrieval request assembled by orchestration."""

    query: str
    tenant_id: str
    knowledge_base_id: str
    user_id: int
    identity_level: IdentityLevel
    top_k: int = 4
    min_score: float = 0.35

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("检索 query 不能为空。")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id 不能为空。")
        if not self.knowledge_base_id.strip():
            raise ValueError("knowledge_base_id 不能为空。")
        if self.user_id < 0:
            raise ValueError("user_id 不能小于 0。")
        if self.top_k <= 0:
            raise ValueError("top_k 必须大于 0。")
        if not 0 <= self.min_score <= 1:
            raise ValueError("min_score 必须在 0 到 1 之间。")


@dataclass(frozen=True, slots=True)
class VectorMatch:
    chunk: KnowledgeChunk
    score: float


@dataclass(frozen=True, slots=True)
class Citation:
    citation_id: str
    source_id: str
    document_id: str
    snippet: str
    page: int | None = None


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    status: RetrievalStatus
    chunks: tuple[KnowledgeChunk, ...] = ()
    citations: tuple[Citation, ...] = ()
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeToolResult:
    """Decoded tool output; SDK/JSON details remain in infrastructure."""

    tool_name: str
    payload: RetrievalResult | KnowledgeCatalogResult | None = None
    failed: bool = False
