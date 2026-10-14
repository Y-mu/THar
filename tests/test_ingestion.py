from __future__ import annotations

import unittest

from langHar.infrastructure.rag.ingest import DocumentIngestor


class FakeStore:
    def __init__(self) -> None:
        self.chunks = []

    async def upsert(self, chunks):
        self.chunks.extend(chunks)
        return tuple(chunk.chunk_id for chunk in chunks)


class TextIngestionTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_splits_and_preserves_scope_acl_and_source(self) -> None:
        store = FakeStore()
        ingestion = DocumentIngestor(store)
        content = ("退款期限为七天。\n" * 180).encode()
        scope = dict(tenant_id="default", knowledge_base_id="default", acl="admin,l2", version="v1")
        count = await ingestion.ingest_file(content, "refund.md", **scope)
        self.assertGreater(count, 1)
        first = list(store.chunks)
        for chunk in first:
            self.assertLessEqual(len(chunk.content), 800)
            self.assertEqual(chunk.metadata["source_id"], "refund.md")
            for key, value in scope.items():
                self.assertEqual(chunk.metadata[key], value)
            self.assertTrue(chunk.metadata["checksum"])
            self.assertTrue(chunk.metadata["position"] is not None)
        await ingestion.ingest_file(content, "refund.md", **scope)
        self.assertEqual([item.chunk_id for item in first], [item.chunk_id for item in store.chunks[count:]])

    async def test_invalid_format_or_text_is_rejected_before_indexing(self) -> None:
        for filename, content in (("file.pdf", b"pdf"), ("empty.txt", b" \n"), ("invalid.txt", b"\xff")):
            with self.subTest(filename=filename):
                store = FakeStore()
                with self.assertRaises(ValueError):
                    await DocumentIngestor(store).ingest_file(
                        content, filename, tenant_id="default", knowledge_base_id="default",
                        acl="admin", version="v1",
                    )
                self.assertEqual(store.chunks, [])
