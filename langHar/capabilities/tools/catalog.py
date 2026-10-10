from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from langHar.core.agent import IdentityLevel


@dataclass(frozen=True, slots=True)
class ToolPermission:
    name: str
    identity_levels: frozenset[IdentityLevel]


@dataclass(frozen=True, slots=True)
class IntentToolSpec:
    tools: tuple[ToolPermission, ...] = ()


ALL_IDENTITIES = frozenset(IdentityLevel)


TOOL_CATALOG: Mapping[str, IntentToolSpec] = MappingProxyType(
    {
        "weather": IntentToolSpec(
            tools=(
                ToolPermission(
                    name="get_weather",
                    identity_levels=ALL_IDENTITIES,
                ),
            ),
        ),
        "calculator": IntentToolSpec(
            tools=(
                ToolPermission(
                    name="calculate",
                    identity_levels=frozenset({IdentityLevel.ADMIN}),
                ),
            ),
        ),
        "general_chat": IntentToolSpec(),
    }
)
