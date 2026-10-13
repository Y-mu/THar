from __future__ import annotations

from pathlib import Path

from langHar.infrastructure.rag.chunk import DocumentChunker
from langHar.infrastructure.rag.loaders import DocumentSourceLoader
from langHar.infrastructure.rag.vector_store import VectorStoreManager


class DocumentIngestor:
    """加载 → 切分 → 入库。"""

    @classmethod
    def ingest(cls, source_dir: str | Path) -> int:
        docs = DocumentSourceLoader.load(source_dir)
        chunks = DocumentChunker.split(docs)
        ids = VectorStoreManager.add_documents(chunks)
        return len(ids)

    @classmethod
    def ingest_documents(cls, documents: list) -> int:
        ids = VectorStoreManager.add_documents(documents)
        return len(ids)