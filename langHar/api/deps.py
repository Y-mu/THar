"""跨 API 模块的最小容器契约。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from fastapi import Request

if TYPE_CHECKING:
    from langHar.api.auth.auth_service import AuthService
    from langHar.api.chat.chat_service import ChatService
    from langHar.api.session.session_manager import SessionManager


class ServiceContainer(Protocol):
    auth_service: AuthService
    chat_service: ChatService
    session_manager: SessionManager

    async def aclose(self) -> None: ...


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container
