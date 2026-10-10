from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class IntentSpec:
    criteria: str


INTENT_CATALOG: Mapping[str, IntentSpec] = MappingProxyType(
    {
        "weather": IntentSpec(
            criteria="查询某地当前天气、温度或天气预报。",
        ),
        "calculator": IntentSpec(
            criteria="要求进行明确的数学计算或算术求值。",
        ),
        "general_chat": IntentSpec(
            criteria="问候、知识问答、闲聊，或其他不需要专用能力的请求。",
        ),
    }
)
