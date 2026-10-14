from __future__ import annotations

import unittest

from langHar.core.agent import IdentityLevel
from langHar.core.knowledge import KnowledgeChunk, RetrievalQuery, VectorMatch
from langHar.orchestration.retrieval_service import RetrievalService


class FakeVectorStore:
    def __init__(self, matches=(), error: Exception | None = None) -> None:
        self.matches = tuple(matches)
        self.error = error

    async def search(self, query: RetrievalQuery):
        if self.error is not None:
            raise self.error
        return self.matches

    async def upsert(self, chunks):
        return tuple(chunk.chunk_id for chunk in chunks)


def request(**kwargs) -> RetrievalQuery:
    return RetrievalQuery(
        query="退款规则",
        tenant_id="tenant-a",
        knowledge_base_id="support",
        user_id=1,
        identity_level=IdentityLevel.L2,
        **kwargs,
    )


class RetrievalServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_filters_scope_acl_and_score_before_citations(self) -> None:
        allowed = KnowledgeChunk(
            "allowed",
            "退款需要在七天内申请。",
            {
                "tenant_id": "tenant-a",
                "knowledge_base_id": "support",
                "source_id": "policy.md",
                "document_id": "doc-1",
                "acl": "l2,admin",
                "page": 2,
            },
        )
        matches = [
            VectorMatch(allowed, 0.9),
            VectorMatch(
                KnowledgeChunk(
                    "wrong-tenant",
                    "不应返回",
                    {
                        "tenant_id": "tenant-b",
                        "knowledge_base_id": "support",
                        "acl": "l2",
                    },
                ),
                0.99,
            ),
            VectorMatch(
                KnowledgeChunk(
                    "low-score",
                    "低分片段",
                    {
                        "tenant_id": "tenant-a",
                        "knowledge_base_id": "support",
                        "acl": "l2",
                    },
                ),
                0.2,
            ),
        ]

        result = await RetrievalService(FakeVectorStore(matches)).search(request())

        self.assertEqual(result.status, "ok")
        self.assertEqual([chunk.chunk_id for chunk in result.chunks], ["allowed"])
        self.assertEqual(result.citations[0].citation_id, "1")
        self.assertEqual(result.citations[0].page, 2)

    async def test_missing_acl_fails_closed(self) -> None:
        chunk = KnowledgeChunk(
            "no-acl",
            "没有 ACL 的文档",
            {"tenant_id": "tenant-a", "knowledge_base_id": "support"},
        )
        result = await RetrievalService(
            FakeVectorStore([VectorMatch(chunk, 0.9)])
        ).search(request())

        self.assertEqual(result.status, "no_evidence")

    async def test_store_failure_is_unavailable(self) -> None:
        with self.assertLogs("langHar.orchestration.retrieval_service", level="ERROR") as logs:
            result = await RetrievalService(
                FakeVectorStore(error=RuntimeError("offline"))
            ).search(request())

        self.assertEqual(result.status, "unavailable")
        self.assertIn("offline", logs.output[0])


if __name__ == "__main__":
    unittest.main()
