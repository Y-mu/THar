from fastapi import Request

from langHar.api.deps import get_container
from langHar.api.chat.chat_service import ChatService


def get_chat_service(request: Request) -> ChatService:
    return get_container(request).chat_service
