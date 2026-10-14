"""Ports used by orchestration for knowledge indexing and retrieval."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from langHar.core.knowledge import (
    KnowledgeCatalogQuery, KnowledgeChunk, RetrievalQuery, VectorMatch,
)


class KnowledgeCatalogStore(Protocol):
    async def list_metadata(
        self, query: KnowledgeCatalogQuery,
    ) -> Sequence[Mapping[str, object]]:
        """Read scoped chunk metadata only, without embedding or vector search."""


class KnowledgeVectorStore(Protocol):
    async def upsert(self, chunks: Sequence[KnowledgeChunk]) -> tuple[str, ...]:
        """Persist chunks and return the IDs written."""

    async def search(self, query: RetrievalQuery) -> Sequence[VectorMatch]:
        """Search using the tenant and knowledge-base scope in ``query``."""
