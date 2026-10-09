from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from langHar.api.dependencies import (
    get_current_user,
    get_session_service,
)
from langHar.api.modules.session.schemas import (
    MessageResponse,
    SessionResponse,
    SessionSummaryResponse,
)
from langHar.api.modules.session.service import (
    ChatSession,
    SessionNotFoundError,
    SessionService,
    StoredMessage,
)
from langHar.api.modules.auth.service import User


router = APIRouter(prefix="/sessions", tags=["sessions"])


def _message_response(message: StoredMessage) -> MessageResponse:
    return MessageResponse(
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


def _session_response(session: ChatSession) -> SessionResponse:
    return SessionResponse(
        session_id=session.session_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[_message_response(message) for message in session.messages],
    )


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    user: User = Depends(get_current_user),
    sessions: SessionService = Depends(get_session_service),
) -> SessionResponse:
    return _session_response(await sessions.create(user.user_id))


@router.get("", response_model=list[SessionSummaryResponse])
async def list_sessions(
    user: User = Depends(get_current_user),
    sessions: SessionService = Depends(get_session_service),
) -> list[SessionSummaryResponse]:
    items = await sessions.list_for_user(user.user_id)
    return [
        SessionSummaryResponse(
            session_id=item.session_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    sessions: SessionService = Depends(get_session_service),
) -> SessionResponse:
    try:
        session = await sessions.get(session_id, user.user_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="会话不存在。") from exc
    return _session_response(session)


