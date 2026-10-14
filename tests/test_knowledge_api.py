from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from langHar.api.app import create_app
from langHar.bootstrap import AppContainer


class FakeKnowledgeIngestion:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def ingest_file(self, content: bytes, filename: str, **kwargs: object) -> int:
        self.calls.append({"content": content, "filename": filename, **kwargs})
        return 3


class KnowledgeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ingestion = FakeKnowledgeIngestion()
        container = AppContainer(
            knowledge_ingestion=self.ingestion,
        )
        self.client_context = TestClient(
            create_app(container_factory=lambda: container)
        )
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def test_document_upload_works_without_login(self) -> None:
        response = self.client.post(
            "/api/v1/knowledge/default/documents",
            files={"file": ("refund.md", "退款规则".encode(), "text/markdown")},
            data={"acl": "admin,l2", "version": "v2"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["chunks_indexed"], 3)
        self.assertEqual(self.ingestion.calls[0]["knowledge_base_id"], "default")
        self.assertEqual(self.ingestion.calls[0]["acl"], "admin,l2")
        self.assertEqual(self.ingestion.calls[0]["version"], "v2")

    def test_unsupported_document_type_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/knowledge/default/documents",
            files={"file": ("script.py", b"print('x')", "text/plain")},
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.ingestion.calls, [])

    def test_mvp_rejects_other_knowledge_bases(self) -> None:
        response = self.client.post(
            "/api/v1/knowledge/other/documents",
            files={"file": ("refund.md", b"refund rules", "text/markdown")},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.ingestion.calls, [])

    def test_removed_pdf_format_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/knowledge/default/documents",
            files={"file": ("refund.pdf", b"pdf", "application/pdf")},
        )
        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.ingestion.calls, [])

