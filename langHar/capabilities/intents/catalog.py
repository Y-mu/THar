from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class IntentSpec:
    criteria: str
    response_policy: str | None = None


INTENT_CATALOG: Mapping[str, IntentSpec] = MappingProxyType(
    {
        "general_chat": IntentSpec(
            criteria="问候、知识问答、闲聊，或其他不需要专用能力的请求。",
        ),
        "knowledge_qa": IntentSpec(
            response_policy="knowledge",
            criteria=(
                "查看受控知识库的文档目录、询问知识库里有什么或有哪些文档，"
                "或者要求基于知识库文档内容回答问题并提供可追溯引用。"
            ),
        ),
    }
)
