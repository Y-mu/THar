from __future__ import annotations

import asyncio
import os
from pathlib import Path
from threading import Lock
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from langHar.core.knowledge import (
    KnowledgeCatalogQuery, KnowledgeChunk, RetrievalQuery, VectorMatch,
)
from langHar.infrastructure.rag.embedding import BGEEmbeddingManager


class ChromaVectorStore:
    """Async Chroma adapter implementing the orchestration vector-store port."""

    def __init__(
        self,
        *,
        persist_directory: str | Path | None = None,
        collection_name: str | None = None,
        embedding_function: Any | None = None,
    ) -> None:
        self._collection_name = collection_name or os.getenv(
            "RAG_COLLECTION_NAME", "rag_documents",
        )
        self._persist_directory = str(
            persist_directory or os.getenv("RAG_PERSIST_DIRECTORY", "chroma_db")
        )
        self._embedding_function = embedding_function
        self._embedding_store: Chroma | None = None
        self._embedding_lock = Lock()
        # 1、元数据连接不加载 Embedding，目录查询不会触发模型下载或推理。
        self._store: Chroma | None = None
        self._metadata_lock = Lock()

    def _open_store(self, *, embedding_function: Any) -> Chroma:
        return Chroma(
            collection_name=self._collection_name,
            embedding_function=embedding_function,
            persist_directory=self._persist_directory,
            collection_metadata={"hnsw:space": "cosine"},
        )

    def _get_metadata_store(self) -> Chroma:
        with self._metadata_lock:
            if self._store is None:
                self._store = self._open_store(embedding_function=None)
            return self._store

    def _get_embedding_store(self) -> Chroma:
        # 2、仅在入库或内容检索时，线程安全地初始化带 Embedding 的连接。
        with self._embedding_lock:
            if self._embedding_store is None:
                embeddings = self._embedding_function
                if embeddings is None:
                    embeddings = BGEEmbeddingManager.get_embeddings()
                self._embedding_store = self._open_store(embedding_function=embeddings)
            return self._embedding_store

    async def list_metadata(
        self, query: KnowledgeCatalogQuery,
    ) -> tuple[dict[str, object], ...]:
        # 3、按租户和知识库读取元数据，正文和向量均不进入目录查询。
        def read_metadata() -> tuple[dict[str, object], ...]:
            rows: list[dict[str, object]] = []
            offset = 0
            batch_size = 500
            while True:
                result = self._get_metadata_store().get(
                    where=_scope_filter(query), include=["metadatas"],
                    limit=batch_size, offset=offset,
                )
                rows.extend(
                    dict(metadata) for metadata in result["metadatas"] or [] if metadata
                )
                count = len(result["ids"])
                if count < batch_size:
                    return tuple(rows)
                offset += count

        return await asyncio.to_thread(read_metadata)

    async def upsert(
        self,
        chunks: list[KnowledgeChunk] | tuple[KnowledgeChunk, ...],
    ) -> tuple[str, ...]:
        documents = [
            Document(page_content=chunk.content, metadata=dict(chunk.metadata))
            for chunk in chunks
        ]
        if not documents:
            return ()
        ids = [chunk.chunk_id for chunk in chunks]
        # Chroma's add operation rejects duplicate IDs. Delete the same IDs
        # first so deterministic chunk IDs make re-indexing repeatable.
        def write_documents() -> None:
            store = self._get_embedding_store()
            store.delete(ids=ids)
            store.add_documents(documents, ids=ids)

        await asyncio.to_thread(write_documents)
        return tuple(ids)

    async def search(self, query: RetrievalQuery) -> tuple[VectorMatch, ...]:
        # The scope is applied in Chroma and checked again by RetrievalService.
        def search_documents():
            return self._get_embedding_store().similarity_search_with_relevance_scores(
                query.query, query.top_k, filter=_scope_filter(query),
            )

        matches = await asyncio.to_thread(search_documents)
        return tuple(
            VectorMatch(
                chunk=KnowledgeChunk(
                    chunk_id=str(document.metadata.get("chunk_id", index)),
                    content=document.page_content,
                    metadata=dict(document.metadata),
                ),
                score=float(score),
            )
            for index, (document, score) in enumerate(matches)
        )


def _scope_filter(query: RetrievalQuery | KnowledgeCatalogQuery) -> dict[str, Any]:
    """Chroma requires multiple metadata conditions to be joined with $and."""
    return {"$and": [
        {"tenant_id": query.tenant_id},
        {"knowledge_base_id": query.knowledge_base_id},
    ]}
