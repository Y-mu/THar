from __future__ import annotations

from langHar.agents.agent import AgentService
from langHar.agents.intent_catalog import INTENT_CATALOG
from langHar.agents.intent_router import IntentRouter
from langHar.agents.jev_intention import JevIntention
from langHar.config import Settings
from langHar.agents.langchain_agent import create_agent_executor


def create_agent_service(settings: Settings | None = None) -> AgentService:
    """在服务端启动阶段调用一次，之后复用返回的 AgentService。"""
    resolved_settings = settings or Settings.from_env()
    intention = JevIntention(
        api_key=resolved_settings.typesafe_api_key,
        catalog=INTENT_CATALOG,
        model=resolved_settings.jev_model,
    )
    router = IntentRouter(
        intention=intention,
        allowed_intents=INTENT_CATALOG.keys(),
        confidence_threshold=resolved_settings.intent_confidence_threshold,
    )
    agent = create_agent_executor(
        resolved_settings,
        INTENT_CATALOG,
    )
    return AgentService(router=router, agent=agent)
