"""跨 API 模块的最小容器契约。"""

from typing import Protocol

from fastapi import Request

from langHar.orchestration.auth_service import AuthService
from langHar.orchestration.chat_service import ChatService
from langHar.orchestration.session_manager import SessionManager


class ServiceContainer(Protocol):
    auth_service: AuthService
    chat_service: ChatService
    session_manager: SessionManager

    async def aclose(self) -> None: ...


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container
