from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from langHar.capabilities.tools.catalog import IntentToolSpec
from langHar.core.agent import IdentityLevel


@dataclass(frozen=True, slots=True)
class ToolAccessDecision:
    accepted: bool
    tools: tuple[str, ...]
    reason: str


class ToolPolicy:
    """同时执行意图工具白名单和身份等级授权。"""

    def __init__(self, catalog: Mapping[str, IntentToolSpec]) -> None:
        self._catalog = catalog

    def authorize(
        self,
        *,
        intent: str,
        identity_level: IdentityLevel,
    ) -> ToolAccessDecision:
        spec = self._catalog.get(intent)
        if spec is None:
            return ToolAccessDecision(False, (), "unknown_intent")

        allowed = tuple(
            permission.name
            for permission in spec.tools
            if identity_level in permission.identity_levels
        )
        if len(allowed) != len(spec.tools):
            return ToolAccessDecision(False, (), "tool_access_denied")
        return ToolAccessDecision(True, allowed, "tool_access_granted")
