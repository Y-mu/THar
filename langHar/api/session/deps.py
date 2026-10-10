from fastapi import Request

from langHar.api.deps import get_container
from langHar.orchestration.session_manager import SessionManager


def get_session_manager(request: Request) -> SessionManager:
    return get_container(request).session_manager
