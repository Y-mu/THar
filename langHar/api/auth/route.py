from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from langHar.api.auth.deps import get_auth_service, get_current_user
from langHar.api.auth.schemas import LoginRequest, LoginResponse, UserResponse
from langHar.api.auth.auth_service import (
    AUTH_COOKIE_NAME,
    AuthService,
    User,
)


router = APIRouter(prefix="/users", tags=["users"])


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    result = service.login(payload.username, payload.password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误。",
        )

    token, user = result
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=service.cookie_max_age,
        httponly=True,
        samesite="lax",
        secure=service.cookie_secure,
        path="/",
    )
    return LoginResponse(
        user_id=user.user_id,
        username=user.username,
        identity_level=user.identity_level,
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        identity_level=user.identity_level,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> Response:
    service.logout(request.cookies.get(AUTH_COOKIE_NAME))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response
