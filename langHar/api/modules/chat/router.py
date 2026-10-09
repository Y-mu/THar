from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette import EventSourceResponse

from langHar.api.dependencies import get_chat_service, get_current_user
from langHar.api.modules.auth.service import User
from langHar.api.modules.chat.schemas import MessageRequest
from langHar.api.modules.chat.service import ChatService
from langHar.api.modules.chat.sse import create_chat_stream_response
from langHar.api.modules.conversation.service import ConversationNotFoundError


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/{conversation_id}/messages",
    response_class=EventSourceResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def send_message(
    conversation_id: str,
    payload: MessageRequest,
    user: User = Depends(get_current_user),
    chat: ChatService = Depends(get_chat_service),
) -> EventSourceResponse:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="消息不能为空。")

    try:
        agent_events = await chat.start_stream(
            conversation_id=conversation_id,
            user_id=user.user_id,
            content=content,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="对话不存在。") from exc

    return create_chat_stream_response(
        agent_events,
        conversation_id=conversation_id,
    )
