from fastapi import HTTPException, Request, status

from langHar.api.deps import get_container
from langHar.orchestration.auth_service import AUTH_COOKIE_NAME, AuthService, User


def get_auth_service(request: Request) -> AuthService:
    return get_container(request).auth_service


def get_current_user(request: Request) -> User:
    service = get_auth_service(request)
    user = service.authenticate(request.cookies.get(AUTH_COOKIE_NAME))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录。",
        )
    return user
