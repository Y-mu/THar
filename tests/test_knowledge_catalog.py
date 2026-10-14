from __future__ import annotations

import tempfile
import asyncio
import unittest
from unittest.mock import patch

from langchain_core.embeddings import Embeddings

from langHar.core.agent import IdentityLevel
from langHar.core.knowledge import KnowledgeCatalogQuery, KnowledgeChunk, RetrievalQuery
from langHar.infrastructure.rag.vector_store import ChromaVectorStore
from langHar.orchestration.retrieval_service import KnowledgeCatalogService


def metadata(**overrides):
    return {
        "tenant_id": "tenant-a", "knowledge_base_id": "support",
        "document_id": "doc-1", "source_id": "policy.md",
        "acl": "admin,l2", "version": "v1", **overrides,
    }


def catalog_query(**overrides):
    return KnowledgeCatalogQuery(
        tenant_id="tenant-a", knowledge_base_id="support", user_id=7,
        identity_level=IdentityLevel.L2, **overrides,
    )


class FakeCatalogStore:
    def __init__(self, rows=(), error=None):
        self.rows = rows
        self.error = error
        self.calls = []

    async def list_metadata(self, query):
        self.calls.append(query)
        if self.error:
            raise self.error
        return self.rows


class KnowledgeCatalogServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_filters_acl_and_scope_before_counting_and_deduplication(self):
        store = FakeCatalogStore([
            metadata(), metadata(), metadata(version="v2"),
            metadata(document_id="hidden", source_id="hidden.md", acl="admin"),
            metadata(tenant_id="tenant-b"), metadata(knowledge_base_id="other"),
            metadata(acl=""), metadata(document_id=""),
        ])
        result = await KnowledgeCatalogService(store).list_documents(catalog_query())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.documents[0].chunk_count, 3)
        self.assertEqual(result.documents[0].versions, ("v1", "v2"))
        self.assertEqual(result.documents[0].source_id, "policy.md")

    async def test_pagination_is_based_on_visible_documents_not_chunks(self):
        store = FakeCatalogStore([
            metadata(document_id="a", source_id="a.md"),
            metadata(document_id="a", source_id="a.md"),
            metadata(document_id="b", source_id="b.md"),
            metadata(document_id="c", source_id="c.md", acl="admin"),
        ])
        service = KnowledgeCatalogService(store)
        first = await service.list_documents(catalog_query(limit=1))
        second = await service.list_documents(catalog_query(limit=1, offset=1))
        self.assertEqual(first.total, 2)
        self.assertEqual(first.documents[0].source_id, "a.md")
        self.assertTrue(first.has_more)
        self.assertEqual(second.documents[0].source_id, "b.md")
        self.assertFalse(second.has_more)

    async def test_no_accessible_documents_is_empty_not_unavailable(self):
        for rows in ([], [metadata(acl="admin")], [metadata(acl=None)]):
            result = await KnowledgeCatalogService(FakeCatalogStore(rows)).list_documents(catalog_query())
            self.assertEqual(result.status, "empty")
            self.assertEqual(result.total, 0)
            self.assertEqual(result.documents, ())

    async def test_store_failure_is_logged_and_fails_closed(self):
        with self.assertLogs("langHar.orchestration.retrieval_service", level="ERROR") as logs:
            result = await KnowledgeCatalogService(
                FakeCatalogStore(error=RuntimeError("offline")),
            ).list_documents(catalog_query())
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.documents, ())
        self.assertIn("offline", logs.output[0])

    def test_invalid_pagination_is_rejected(self):
        for kwargs in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
            with self.assertRaises(ValueError):
                catalog_query(**kwargs)


class FakeEmbeddings(Embeddings):
    """Fixed local vectors; never load a model or call an embedding API."""

    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0, 0.0]


class ChromaCatalogTests(unittest.IsolatedAsyncioTestCase):
    async def test_metadata_and_search_use_valid_scope_filters_without_real_embedding(self):
        with tempfile.TemporaryDirectory(prefix="thar-chroma-test-") as directory:
            store = await asyncio.to_thread(
                ChromaVectorStore, persist_directory=directory,
                embedding_function=FakeEmbeddings(),
            )
            await store.upsert([
                KnowledgeChunk("allowed", "退款规则", metadata()),
                KnowledgeChunk("other-tenant", "不可见", metadata(tenant_id="tenant-b")),
                KnowledgeChunk("other-kb", "不可见", metadata(knowledge_base_id="other")),
            ])
            # Reopen with no embedding function; catalog must not initialize BGE.
            with patch(
                "langHar.infrastructure.rag.vector_store.BGEEmbeddingManager.get_embeddings",
                side_effect=AssertionError("catalog must not load BGE"),
            ) as get_embeddings:
                catalog_store = await asyncio.to_thread(ChromaVectorStore, persist_directory=directory)
                rows = await catalog_store.list_metadata(catalog_query())
                get_embeddings.assert_not_called()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["tenant_id"], "tenant-a")
            matches = await store.search(RetrievalQuery(
                query="退款", tenant_id="tenant-a", knowledge_base_id="support",
                user_id=7, identity_level=IdentityLevel.L2,
            ))
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].chunk.content, "退款规则")

    async def test_metadata_reader_continues_past_first_batch(self):
        class MetadataConnection:
            def get(self, *, where, include, limit, offset):
                from chromadb.api.types import validate_where
                validate_where(where)
                self_test.assertEqual(include, ["metadatas"])
                count = 500 if offset == 0 else 1
                return {"ids": [str(offset + i) for i in range(count)], "metadatas": [metadata()] * count}

        self_test = self
        with patch("langHar.infrastructure.rag.vector_store.Chroma", return_value=MetadataConnection()):
            store = ChromaVectorStore()
            rows = await store.list_metadata(catalog_query())
        self.assertEqual(len(rows), 501)


if __name__ == "__main__":
    unittest.main()
