from __future__ import annotations

import ast
import unittest
from collections.abc import Sequence
from pathlib import Path

from fastapi.testclient import TestClient

from langHar.agents.core.chat_message import ChatMessage
from langHar.api.app import create_app
from langHar.api.modules.auth.service import AUTH_COOKIE_NAME, AuthService
from langHar.api.modules.session.service import SessionNotFoundError, SessionService


class FakeAgentService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Sequence[ChatMessage]]] = []
        self.closed = False

    async def handle_message(
        self,
        message: str,
        *,
        session_id: str,
        history: Sequence[ChatMessage] = (),
    ) -> str:
        self.calls.append((message, session_id, history))
        return f"回答：{message}"

    async def aclose(self) -> None:
        self.closed = True


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = FakeAgentService()
        app = create_app(
            agent_service_factory=lambda: self.agent,
            auth_service_factory=lambda: AuthService(
                username="admin",
                password="password",
            ),
        )
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def login(self) -> None:
        response = self.client.post(
            "/api/v1/users/login",
            json={"username": "admin", "password": "password"},
        )
        self.assertEqual(response.status_code, 200)

    def test_login_sets_httponly_cookie_and_me_uses_it(self) -> None:
        response = self.client.post(
            "/api/v1/users/login",
            json={"username": "admin", "password": "password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(AUTH_COOKIE_NAME, response.cookies)
        set_cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", set_cookie)
        self.assertIn("samesite=lax", set_cookie)
        me = self.client.get("/api/v1/users/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "admin")

    def test_invalid_login_does_not_set_cookie(self) -> None:
        response = self.client.post(
            "/api/v1/users/login",
            json={"username": "admin", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertNotIn(AUTH_COOKIE_NAME, response.cookies)

    def test_session_endpoints_require_login(self) -> None:
        response = self.client.post("/api/v1/sessions")

        self.assertEqual(response.status_code, 401)

    def test_create_session_chat_and_get_history(self) -> None:
        self.login()
        created = self.client.post("/api/v1/sessions")
        self.assertEqual(created.status_code, 201)
        session_id = created.json()["session_id"]

        reply = self.client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"content": "你好"},
        )
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.json()["message"]["content"], "回答：你好")

        session = self.client.get(f"/api/v1/sessions/{session_id}")
        self.assertEqual(session.status_code, 200)
        self.assertEqual(
            [message["role"] for message in session.json()["messages"]],
            ["user", "assistant"],
        )
        self.assertEqual(len(self.agent.calls), 1)
        self.assertEqual(self.agent.calls[0][2], ())

        second = self.client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"content": "继续"},
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(self.agent.calls[1][2]), 2)

    def test_logout_invalidates_cookie(self) -> None:
        self.login()
        response = self.client.post("/api/v1/users/logout")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/users/me").status_code, 401)

    def test_lifespan_closes_agent(self) -> None:
        self.assertFalse(self.agent.closed)
        self.client_context.__exit__(None, None, None)
        self.assertTrue(self.agent.closed)
        self.client_context = _AlreadyClosedContext()


class _AlreadyClosedContext:
    def __exit__(self, *args: object) -> None:
        return None


class SessionOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_cannot_read_another_users_session(self) -> None:
        service = SessionService()
        session = await service.create("user-a")

        with self.assertRaises(SessionNotFoundError):
            await service.get(session.session_id, "user-b")


class ApiModuleBoundaryTests(unittest.TestCase):
    def test_session_module_does_not_depend_on_agent_module(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        session_module = project_root / "langHar" / "api" / "modules" / "session"
        violations: list[str] = []

        for path in session_module.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module.startswith("langHar.agents"):
                        violations.append(path.name)
                elif isinstance(node, ast.Import):
                    if any(
                        name.name.startswith("langHar.agents")
                        for name in node.names
                    ):
                        violations.append(path.name)

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
