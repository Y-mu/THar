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


TOOL_CATALOG: Mapping[str, IntentToolSpec] = MappingProxyType(
    {
        "general_chat": IntentToolSpec(),
        "knowledge_qa": IntentToolSpec(
            tools=(
                ToolPermission(
                    name="knowledge_list_documents",
                    identity_levels=frozenset({
                        IdentityLevel.ADMIN, IdentityLevel.L1, IdentityLevel.L2,
                    }),
                ),
                ToolPermission(
                    name="knowledge_search",
                    identity_levels=frozenset({
                        IdentityLevel.ADMIN,
                        IdentityLevel.L1,
                        IdentityLevel.L2,
                    }),
                ),
            ),
        ),
    }
)
