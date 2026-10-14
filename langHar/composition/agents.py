"""无业务工具的普通对话 Agent，由主图意图门调用。"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, NotRequired

from langchain.agents import create_agent
from langchain.agents.middleware import AgentState, ModelRequest, ModelResponse, dynamic_prompt, wrap_model_call
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from langHar.orchestration.messages import MODEL_UNAVAILABLE_MESSAGE

logger = logging.getLogger(__name__)


class ChatState(AgentState):
    intent: NotRequired[str]


def create_chat_agent(*, model: BaseChatModel, prompts: Mapping[str, str]) -> Any:
    @dynamic_prompt
    def intent_prompt(request: ModelRequest) -> str:
        return prompts[str(request.state.get("intent"))]

    @wrap_model_call
    async def handle_model(request: ModelRequest, handler: Any) -> Any:
        try:
            response = await handler(request)
        except Exception:
            logger.exception("模型调用失败")
            return ModelResponse(result=[AIMessage(content=MODEL_UNAVAILABLE_MESSAGE)])
        if any(message.tool_calls for message in response.result if isinstance(message, AIMessage)):
            raise PermissionError("普通对话 Agent 不允许调用业务工具。")
        return response

    return create_agent(
        model, tools=[], middleware=[handle_model, intent_prompt],
        state_schema=ChatState, name="chat",
    )
