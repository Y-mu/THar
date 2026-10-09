"""FastAPI 路由依赖。"""

from fastapi import HTTPException, Request, status

from langHar.api.modules.auth.service import AUTH_COOKIE_NAME, AuthService, User
from langHar.api.modules.chat.service import ChatService
from langHar.api.modules.conversation.service import ConversationService


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_conversation_service(request: Request) -> ConversationService:
    return request.app.state.conversation_service


def get_current_user(request: Request) -> User:
    service = get_auth_service(request)
    user = service.authenticate(request.cookies.get(AUTH_COOKIE_NAME))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录。",
        )
    return user
