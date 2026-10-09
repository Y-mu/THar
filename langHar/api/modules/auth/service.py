from __future__ import annotations

import asyncio
import hmac
import os
import secrets
import time
from dataclasses import dataclass


AUTH_COOKIE_NAME = "langhar_auth"
AUTH_COOKIE_MAX_AGE = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class User:
    user_id: str
    username: str


class AuthService:
    """验证用户并管理 Web 登录会话。"""

    def __init__(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        configured_username = username or os.getenv("LANGHAR_USERNAME", "admin")
        configured_password = password or os.getenv("LANGHAR_PASSWORD", "password")
        self._user = User(user_id="user-1", username=configured_username)
        self._password = configured_password
        self.cookie_max_age = AUTH_COOKIE_MAX_AGE
        self.cookie_secure = os.getenv(
            "LANGHAR_COOKIE_SECURE",
            "false",
        ).lower() in {"1", "true", "yes"}
        self._auth_sessions: dict[str, tuple[User, float]] = {}
        self._lock = asyncio.Lock()

    async def login(self, username: str, password: str) -> tuple[str, User] | None:
        username_matches = hmac.compare_digest(
            username.encode(),
            self._user.username.encode(),
        )
        password_matches = hmac.compare_digest(
            password.encode(),
            self._password.encode(),
        )
        if not username_matches or not password_matches:
            return None

        token = secrets.token_urlsafe(32)
        async with self._lock:
            self._auth_sessions[token] = (
                self._user,
                time.monotonic() + self.cookie_max_age,
            )
        return token, self._user

    async def authenticate(self, token: str | None) -> User | None:
        if not token:
            return None
        async with self._lock:
            auth_session = self._auth_sessions.get(token)
            if auth_session is None:
                return None
            user, expires_at = auth_session
            if expires_at <= time.monotonic():
                self._auth_sessions.pop(token, None)
                return None
            return user

    async def logout(self, token: str | None) -> None:
        if not token:
            return
        async with self._lock:
            self._auth_sessions.pop(token, None)

