from __future__ import annotations

from typing import Protocol


class KnowledgeIngestionPort(Protocol):
    """Knowledge API consumes this port without knowing the storage backend."""

    async def ingest_file(
        self,
        content: bytes,
        filename: str,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        acl: str,
        version: str,
    ) -> int: ...
