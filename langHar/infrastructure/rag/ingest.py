from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from langHar.core.knowledge import KnowledgeChunk, SUPPORTED_DOCUMENT_SUFFIXES
from langHar.orchestration.retrieval_ports import KnowledgeVectorStore


class DocumentIngestor:
    """加载 → 切分 → 入库。"""

    def __init__(self, store: KnowledgeVectorStore) -> None:
        self._store = store

    async def ingest_file(
        self,
        content: bytes,
        filename: str,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        acl: str,
        version: str,
    ) -> int:
        chunks = await asyncio.to_thread(
            self._prepare_chunks, content, filename, tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id, acl=acl, version=version,
        )
        return len(await self._store.upsert(chunks))

    @staticmethod
    def _prepare_chunks(
        content: bytes,
        filename: str,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        acl: str,
        version: str,
    ) -> list[KnowledgeChunk]:
        source_id = Path(filename).name
        if Path(source_id).suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES:
            raise ValueError("MVP 仅支持 Markdown/TXT 文档。")
        text = content.decode("utf-8")
        if not text.strip():
            raise ValueError("文档内容不能为空。")
        chunks = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120).create_documents(
            [text], metadatas=[{"source": source_id}],
        )
        result: list[KnowledgeChunk] = []
        for index, chunk in enumerate(chunks):
            source_id = str(chunk.metadata.get("source", "unknown"))
            document_id = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:24]
            checksum = hashlib.sha256(chunk.page_content.encode("utf-8")).hexdigest()
            chunk_id = hashlib.sha256(
                f"{document_id}:{version}:{checksum}:{index}".encode("utf-8")
            ).hexdigest()
            metadata = {
                **chunk.metadata,
                "tenant_id": tenant_id,
                "knowledge_base_id": knowledge_base_id,
                "source_id": source_id,
                "document_id": document_id,
                "version": version,
                "checksum": checksum,
                "chunk_id": chunk_id,
                "acl": acl,
                "position": index,
            }
            result.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    content=chunk.page_content,
                    metadata=metadata,
                )
            )
        return result
