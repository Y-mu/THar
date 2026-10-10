from __future__ import annotations

from pydantic import BaseModel, Field

from langHar.agents.core.agent_context import IdentityLevel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    user_id: int
    username: str
    identity_level: IdentityLevel


class LoginResponse(UserResponse):
    message: str = "登录成功"
