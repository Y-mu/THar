from __future__ import annotations

import secrets
from dataclasses import dataclass


AUTH_COOKIE_NAME = "langhar_auth"
AUTH_COOKIE_MAX_AGE = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class User:
    user_id: str
    username: str


class AuthService:
    """多用户、内存版的最小登录服务。"""

    def __init__(self) -> None:
        self.cookie_max_age = AUTH_COOKIE_MAX_AGE
        self.cookie_secure = False
        self._auth_sessions: dict[str, User] = {}

    def login(self, username: str, password: str) -> tuple[str, User] | None:
        accounts = {
            "admin": {"user_id": "user-1", "password": "password"},
            "tony": {"user_id": "user-2", "password": "123456"},
        }
        account = accounts.get(username)
        if account is None or password != account["password"]:
            return None

        user = User(user_id=account["user_id"], username=username)
        token = secrets.token_urlsafe(32)
        self._auth_sessions[token] = user
        return token, user

    def authenticate(self, token: str | None) -> User | None:
        if not token:
            return None
        return self._auth_sessions.get(token)

    def logout(self, token: str | None) -> None:
        if not token:
            return
        self._auth_sessions.pop(token, None)
