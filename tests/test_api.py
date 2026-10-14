from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from langHar.api.app import create_app
from langHar.bootstrap import AppContainer


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client_context = TestClient(create_app(container_factory=AppContainer))
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def test_login_endpoints_are_removed(self) -> None:
        for method, path in (
            ("POST", "/api/v1/users/login"),
            ("GET", "/api/v1/users/me"),
            ("POST", "/api/v1/users/logout"),
        ):
            self.assertEqual(self.client.request(method, path).status_code, 404)

    def test_chat_and_sessions_are_owned_by_langgraph_server(self) -> None:
        self.assertEqual(self.client.post("/api/v1/conversations").status_code, 404)
        self.assertEqual(self.client.post("/api/v1/chat/old/messages", json={"content": "你好"}).status_code, 404)

    def test_health_endpoints(self) -> None:
        self.assertEqual(self.client.get("/health/live").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/health/ready").json(), {"status": "ready"})
