from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from langchain_chroma import Chroma

from langHar.infrastructure.rag.embedding import BGEEmbeddingManager


class VectorStoreManager:
    """Chroma 向量存储的单例管理器。"""

    PERSIST_DIR = Path("chroma_db")
    COLLECTION_NAME = "rag_documents"

    _instance: Optional[Chroma] = None

    @classmethod
    def get_store(cls) -> Chroma:
        if cls._instance is None:
            cls._instance = Chroma(
                collection_name=cls.COLLECTION_NAME,
                embedding_function=BGEEmbeddingManager.get_embeddings(),
                persist_directory=str(cls.PERSIST_DIR),
            )
        return cls._instance

    @classmethod
    def add_documents(cls, documents: list[Any], ids: list[str] | None = None) -> list[str]:
        return cls.get_store().add_documents(documents, ids=ids)

    @classmethod
    def similarity_search(cls, query: str, k: int = 4) -> list[Any]:
        return cls.get_store().similarity_search(query, k=k)

    @classmethod
    def get_retriever(cls, k: int = 4) -> Any:
        return cls.get_store().as_retriever(search_kwargs={"k": k})