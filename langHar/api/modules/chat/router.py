from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from langHar.api.dependencies import get_chat_service, get_current_user
from langHar.api.modules.auth.service import User
from langHar.api.modules.chat.schemas import ChatResponse, MessageRequest
from langHar.api.modules.chat.service import ChatService
from langHar.api.modules.session.schemas import MessageResponse
from langHar.api.modules.session.service import SessionNotFoundError, StoredMessage


router = APIRouter(prefix="/sessions", tags=["chat"])


def _message_response(message: StoredMessage) -> MessageResponse:
    return MessageResponse(
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


@router.post("/{session_id}/messages", response_model=ChatResponse)
async def send_message(
    session_id: str,
    payload: MessageRequest,
    user: User = Depends(get_current_user),
    chat: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="消息不能为空。")
    try:
        answer = await chat.send_message(
            session_id=session_id,
            user_id=user.user_id,
            content=content,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="会话不存在。") from exc
    return ChatResponse(
        session_id=session_id,
        message=_message_response(answer),
    )
