from __future__ import annotations

import secrets
from dataclasses import dataclass

from langHar.core.agent import IdentityLevel


AUTH_COOKIE_NAME = "langhar_auth"
AUTH_COOKIE_MAX_AGE = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class User:
    user_id: int
    username: str
    identity_level: IdentityLevel


class AuthService:
    """多用户、内存版的最小登录服务。"""

    def __init__(self) -> None:
        self.cookie_max_age = AUTH_COOKIE_MAX_AGE
        self.cookie_secure = False
        self._auth_sessions: dict[str, User] = {}

    def login(self, username: str, password: str) -> tuple[str, User] | None:
        accounts = {
            "admin": {
                "user_id": 0,
                "password": "password",
                "identity_level": IdentityLevel.ADMIN,
            },
            "tony": {
                "user_id": 1,
                "password": "123456",
                "identity_level": IdentityLevel.L2,
            },
        }
        account = accounts.get(username)
        if account is None or password != account["password"]:
            return None

        user = User(
            user_id=account["user_id"],
            username=username,
            identity_level=account["identity_level"],
        )
        token = secrets.token_urlsafe(32)
        self._auth_sessions[token] = user
        return token, user

    def authenticate(self, token: str | None) -> User | None:
        if not token:
            return None
        return self._auth_sessions.get(token)

    def logout(self, token: str | None) -> None:
        if token:
            self._auth_sessions.pop(token, None)
