from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PromptSpec:
    system_prompt: str


PROMPT_REGISTRY: Mapping[str, PromptSpec] = MappingProxyType(
    {
        "weather": PromptSpec(
            system_prompt=(
                "你是天气助手。必须调用 get_weather 查询用户指定的位置，"
                "然后用简洁中文回答。"
            ),
        ),
        "calculator": PromptSpec(
            system_prompt=(
                "你是计算助手。必须调用 calculate 完成算术计算，"
                "不要自行执行代码或调用其他工具。"
            ),
        ),
        "general_chat": PromptSpec(
            system_prompt="你是一个简洁、友好的中文助手。",
        ),
    }
)
