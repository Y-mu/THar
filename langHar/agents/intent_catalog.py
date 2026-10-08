from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class IntentSpec:
    criteria: str
    system_prompt: str
    tools: tuple[str, ...] = ()


INTENT_CATALOG: Mapping[str, IntentSpec] = MappingProxyType(
    {
        "weather": IntentSpec(
            criteria="查询某地当前天气、温度或天气预报。",
            system_prompt=(
                "你是天气助手。必须调用 get_weather 查询用户指定的位置，"
                "然后用简洁中文回答。"
            ),
            tools=("get_weather",),
        ),
        "calculator": IntentSpec(
            criteria="要求进行明确的数学计算或算术求值。",
            system_prompt=(
                "你是计算助手。必须调用 calculate 完成算术计算，"
                "不要自行执行代码或调用其他工具。"
            ),
            tools=("calculate",),
        ),
        "general_chat": IntentSpec(
            criteria="问候、知识问答、闲聊，或其他不需要专用能力的请求。",
            system_prompt="你是一个简洁、友好的中文助手。",
        ),
    }
)
