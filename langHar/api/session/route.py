from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from langHar.api.auth import get_current_user
from langHar.api.session.deps import get_session_manager
from langHar.api.session.schemas import (
    ConversationResponse,
    ConversationSummaryResponse,
    MessageResponse,
)
from langHar.orchestration.auth_service import User
from langHar.orchestration.session_manager import (
    Conversation,
    ConversationNotFoundError,
    SessionManager,
    StoredMessage,
)


router = APIRouter(prefix="/conversations", tags=["conversations"])


def _message_response(message: StoredMessage) -> MessageResponse:
    return MessageResponse(
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


def _conversation_response(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[_message_response(message) for message in conversation.messages],
    )


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    user: User = Depends(get_current_user),
    sessions: SessionManager = Depends(get_session_manager),
) -> ConversationResponse:
    return _conversation_response(await sessions.create(user.user_id))


@router.get("", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    user: User = Depends(get_current_user),
    sessions: SessionManager = Depends(get_session_manager),
) -> list[ConversationSummaryResponse]:
    items = await sessions.list_for_user(user.user_id)
    return [
        ConversationSummaryResponse(
            conversation_id=item.conversation_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    sessions: SessionManager = Depends(get_session_manager),
) -> ConversationResponse:
    try:
        conversation = await sessions.get(conversation_id, user.user_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="对话不存在。") from exc
    return _conversation_response(conversation)
