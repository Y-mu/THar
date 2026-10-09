from __future__ import annotations

import ast
import json
import unittest
from collections.abc import Sequence
from pathlib import Path

from fastapi.testclient import TestClient

from langHar.agents.core.agent_event import AgentEvent
from langHar.agents.core.chat_message import ChatMessage
from langHar.api.app import create_app
from langHar.api.modules.auth.service import AUTH_COOKIE_NAME, AuthService
from langHar.api.modules.chat.router import router as chat_router
from langHar.api.modules.conversation.router import router as conversation_router
from langHar.api.modules.conversation.service import (
    ConversationNotFoundError,
    ConversationService,
)


class FakeAgentService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Sequence[ChatMessage]]] = []
        self.closed = False
        self.include_tool_events = False

    async def stream_message(
        self,
        message: str,
        *,
        session_id: str,
        history: Sequence[ChatMessage] = (),
    ):
        self.calls.append((message, session_id, history))
        answer = f"回答：{message}"
        if self.include_tool_events:
            yield AgentEvent(type="tool_start", content="", name="calculator")
            yield AgentEvent(type="tool_end", content="2", name="calculator")
        yield AgentEvent(type="token", content=answer)
        yield AgentEvent(type="final", content=answer)

    async def aclose(self) -> None:
        self.closed = True


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = FakeAgentService()
        app = create_app(
            agent_service_factory=lambda: self.agent,
            auth_service_factory=AuthService,
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

    def test_conversation_endpoints_require_login(self) -> None:
        response = self.client.post("/api/v1/conversations")

        self.assertEqual(response.status_code, 401)

    def test_create_conversation_chat_and_get_history(self) -> None:
        self.login()
        created = self.client.post("/api/v1/conversations")
        self.assertEqual(created.status_code, 201)
        conversation_id = created.json()["conversation_id"]

        reply = self.client.post(
            f"/api/v1/chat/{conversation_id}/messages",
            json={"content": "你好"},
        )
        self.assertEqual(reply.status_code, 200)
        self.assertTrue(reply.headers["content-type"].startswith("text/event-stream"))
        events = _sse_payloads(reply.text)
        self.assertEqual([event["type"] for event in events], ["token", "final"])
        self.assertEqual(events[-1]["content"], "回答：你好")
        self.assertEqual(events[-1]["conversation_id"], conversation_id)
        self.assertEqual(events[-1]["sequence"], 2)
        self.assertEqual(events[0]["run_id"], events[-1]["run_id"])

        conversation = self.client.get(
            f"/api/v1/conversations/{conversation_id}"
        )
        self.assertEqual(conversation.status_code, 200)
        self.assertEqual(
            [message["role"] for message in conversation.json()["messages"]],
            ["user", "assistant"],
        )
        self.assertEqual(len(self.agent.calls), 1)
        self.assertEqual(self.agent.calls[0][2], ())

        second = self.client.post(
            f"/api/v1/chat/{conversation_id}/messages",
            json={"content": "继续"},
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            [event["type"] for event in _sse_payloads(second.text)],
            ["token", "final"],
        )
        self.assertEqual(len(self.agent.calls[1][2]), 2)

    def test_logout_invalidates_cookie(self) -> None:
        self.login()
        response = self.client.post("/api/v1/users/logout")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/users/me").status_code, 401)

    def test_chat_stream_preserves_tool_events(self) -> None:
        self.login()
        self.agent.include_tool_events = True
        conversation_id = self.client.post("/api/v1/conversations").json()[
            "conversation_id"
        ]

        response = self.client.post(
            f"/api/v1/chat/{conversation_id}/messages",
            json={"content": "1+1"},
        )

        events = _sse_payloads(response.text)
        self.assertEqual(
            [event["type"] for event in events],
            ["tool_start", "tool_end", "token", "final"],
        )
        self.assertEqual(events[0]["name"], "calculator")
        self.assertEqual(events[1]["content"], "2")

    def test_users_have_isolated_conversations(self) -> None:
        self.login()
        created = self.client.post("/api/v1/conversations")
        admin_conversation_id = created.json()["conversation_id"]

        tony_login = self.client.post(
            "/api/v1/users/login",
            json={"username": "tony", "password": "123456"},
        )
        self.assertEqual(tony_login.status_code, 200)
        self.assertEqual(tony_login.json()["user_id"], "user-2")

        response = self.client.get(
            f"/api/v1/conversations/{admin_conversation_id}"
        )
        self.assertEqual(response.status_code, 404)

    def test_lifespan_closes_agent(self) -> None:
        self.assertFalse(self.agent.closed)
        self.client_context.__exit__(None, None, None)
        self.assertTrue(self.agent.closed)
        self.client_context = _AlreadyClosedContext()


class _AlreadyClosedContext:
    def __exit__(self, *args: object) -> None:
        return None


def _sse_payloads(body: str) -> list[dict[str, object]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
        elif isinstance(node, ast.Import):
            modules.update(name.name for name in node.names)
    return modules


class ConversationOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_cannot_read_another_users_conversation(self) -> None:
        service = ConversationService()
        conversation = await service.create("user-a")

        with self.assertRaises(ConversationNotFoundError):
            await service.get(conversation.conversation_id, "user-b")


class ApiModuleBoundaryTests(unittest.TestCase):
    def test_conversation_and_chat_routers_use_distinct_prefixes(self) -> None:
        self.assertEqual(conversation_router.prefix, "/conversations")
        self.assertEqual(chat_router.prefix, "/chat")

    def test_conversation_module_does_not_depend_on_agent_module(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        conversation_module = (
            project_root / "langHar" / "api" / "modules" / "conversation"
        )
        violations: list[str] = []

        for path in conversation_module.glob("*.py"):
            if any(
                module.startswith("langHar.agents")
                for module in _imported_modules(path)
            ):
                violations.append(path.name)

        self.assertEqual(violations, [])

    def test_chat_router_only_handles_http_coordination(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        router_path = (
            project_root / "langHar" / "api" / "modules" / "chat" / "router.py"
        )
        modules = _imported_modules(router_path)
        source = router_path.read_text(encoding="utf-8")

        self.assertTrue({"logging", "uuid", "collections.abc"}.isdisjoint(modules))
        self.assertNotIn("ChatResponse", source)
        self.assertNotIn("ServerSentEvent", source)

    def test_chat_schemas_do_not_encode_transport_or_agent_events(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        schemas_path = (
            project_root / "langHar" / "api" / "modules" / "chat" / "schemas.py"
        )
        modules = _imported_modules(schemas_path)

        self.assertFalse(
            any(module.startswith("langHar.agents") for module in modules)
        )
        self.assertFalse(
            any(module.startswith("sse_starlette") for module in modules)
        )


if __name__ == "__main__":
    unittest.main()
