from __future__ import annotations

from dataclasses import dataclass, field

from langHar.api.auth.auth_service import AuthService
from langHar.api.chat.chat_service import ChatService
from langHar.api.session.session_manager import SessionManager
from langHar.capabilities.intents import INTENT_CATALOG
from langHar.capabilities.prompts import PROMPT_REGISTRY
from langHar.capabilities.tools import TOOL_CATALOG, TOOL_REGISTRY, ToolPolicy
from langHar.config import Settings
from langHar.infrastructure.intent_recognition import JevIntentRecognizer
from langHar.infrastructure.llm.langchain_agent import create_agent_executor
from langHar.orchestration.agent_service import AgentService
from langHar.orchestration.intent_router import IntentRouter


@dataclass(slots=True)
class AppContainer:
    auth_service: AuthService
    chat_service: ChatService
    session_manager: SessionManager
    _agent_service: AgentService = field(repr=False)

    async def aclose(self) -> None:
        await self._agent_service.aclose()


def create_agent_service(settings: Settings) -> AgentService:
    _validate_catalogs()
    recognizer = JevIntentRecognizer(
        api_key=settings.typesafe_api_key,
        catalog=INTENT_CATALOG,
        model=settings.jev_model,
    )
    intent_router = IntentRouter(
        recognizer=recognizer,
        allowed_intents=INTENT_CATALOG.keys(),
        confidence_threshold=settings.intent_confidence_threshold,
    )
    configured_tool_names = {
        permission.name
        for spec in TOOL_CATALOG.values()
        for permission in spec.tools
    }
    executor = create_agent_executor(
        settings,
        system_prompts={
            name: spec.system_prompt
            for name, spec in PROMPT_REGISTRY.items()
        },
        tools=[TOOL_REGISTRY[name] for name in sorted(configured_tool_names)],
    )
    return AgentService(
        intent_router=intent_router,
        tool_policy=ToolPolicy(TOOL_CATALOG),
        agent=executor,
    )


def create_container(settings: Settings | None = None) -> AppContainer:
    resolved_settings = settings or Settings.from_env()
    agent_service = create_agent_service(resolved_settings)
    auth_service = AuthService()
    session_manager = SessionManager()
    chat_service = ChatService(
        sessions=session_manager,
        agent=agent_service,
    )
    return AppContainer(
        auth_service=auth_service,
        chat_service=chat_service,
        session_manager=session_manager,
        _agent_service=agent_service,
    )


def _validate_catalogs() -> None:
    intents = set(INTENT_CATALOG)
    prompts = set(PROMPT_REGISTRY)
    tool_policies = set(TOOL_CATALOG)
    if intents != prompts or intents != tool_policies:
        raise ValueError(
            "Intent、Prompt 和 Tool catalog 的意图集合必须一致。"
        )

    configured_tools = {
        permission.name
        for spec in TOOL_CATALOG.values()
        for permission in spec.tools
    }
    missing_tools = configured_tools.difference(TOOL_REGISTRY)
    if missing_tools:
        raise ValueError(
            f"TOOL_CATALOG 引用了未注册工具："
            f"{', '.join(sorted(missing_tools))}。"
        )
