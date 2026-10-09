from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from langHar.api.dependencies import (
    get_conversation_service,
    get_current_user,
)
from langHar.api.modules.auth.service import User
from langHar.api.modules.conversation.schemas import (
    ConversationResponse,
    ConversationSummaryResponse,
    MessageResponse,
)
from langHar.api.modules.conversation.service import (
    Conversation,
    ConversationNotFoundError,
    ConversationService,
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
    conversations: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    return _conversation_response(await conversations.create(user.user_id))


@router.get("", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    user: User = Depends(get_current_user),
    conversations: ConversationService = Depends(get_conversation_service),
) -> list[ConversationSummaryResponse]:
    items = await conversations.list_for_user(user.user_id)
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
    conversations: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    try:
        conversation = await conversations.get(conversation_id, user.user_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="对话不存在。") from exc
    return _conversation_response(conversation)
