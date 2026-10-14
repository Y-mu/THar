from __future__ import annotations

import json
import os
from dataclasses import dataclass

from langHar.api.app import create_app
from langHar.api.knowledge.ports import KnowledgeIngestionPort
from langHar.capabilities.intents import INTENT_CATALOG
from langHar.capabilities.knowledge.policy import RESPONSE_POLICY_REGISTRY
from langHar.capabilities.prompts import PROMPT_REGISTRY
from langHar.capabilities.prompts.registry import KNOWLEDGE_COMPOSE_PROMPT
from langHar.capabilities.tools import TOOL_CATALOG, TOOL_REGISTRY, ToolPolicy
from langHar.composition.agents import create_chat_agent
from langHar.composition.graph import build_agent_graph
from langHar.composition.knowledge_flow import build_knowledge_node
from langHar.config import Settings
from langHar.core.agent import IdentityLevel
from langHar.infrastructure.intent_recognition import JevIntentRecognizer
from langHar.infrastructure.llm.providers import create_chat_model
from langHar.infrastructure.rag.ingest import DocumentIngestor
from langHar.infrastructure.rag.vector_store import ChromaVectorStore
from langHar.orchestration.intent_router import IntentRouter
from langHar.orchestration.retrieval_service import KnowledgeCatalogService, RetrievalService


@dataclass(slots=True)
class AppContainer:
    knowledge_ingestion: KnowledgeIngestionPort | None = None


def create_agent_graph(settings: Settings) -> object:
    """唯一 Agent 运行链；检查点和流式协议交给 LangGraph Server。"""
    _validate_catalogs()
    store = ChromaVectorStore()
    retrieval_service = RetrievalService(store)
    catalog_service = KnowledgeCatalogService(store)
    model = create_chat_model(settings)
    agents = create_chat_agent(
        model=model,
        prompts={name: spec.system_prompt for name, spec in PROMPT_REGISTRY.items()},
    )
    knowledge = build_knowledge_node(
        model=model,
        search=retrieval_service.search,
        list_documents=catalog_service.list_documents,
        policy=RESPONSE_POLICY_REGISTRY["knowledge"],
        plan_prompts={
            name: PROMPT_REGISTRY[name].system_prompt
            for name, spec in INTENT_CATALOG.items() if spec.response_policy == "knowledge"
        },
        compose_prompt=KNOWLEDGE_COMPOSE_PROMPT,
    )
    recognizer = JevIntentRecognizer(
        api_key=settings.typesafe_api_key,
        catalog=INTENT_CATALOG,
        model=settings.jev_model,
    )
    return build_agent_graph(
        intent_router=IntentRouter(
            recognizer=recognizer,
            allowed_intents=INTENT_CATALOG.keys(),
            confidence_threshold=settings.intent_confidence_threshold,
        ),
        tool_policy=ToolPolicy(TOOL_CATALOG),
        agents=agents,
        knowledge=knowledge,
        knowledge_intents=frozenset(
            name for name, spec in INTENT_CATALOG.items() if spec.response_policy == "knowledge"
        ),
    )


def create_container() -> AppContainer:
    return AppContainer(
        knowledge_ingestion=DocumentIngestor(ChromaVectorStore()),
    )


def create_http_app():
    """复用 Server 的 CORS 配置，在本地开发模式接受 Studio 私有网络预检。"""
    http_config = json.loads(os.getenv("LANGGRAPH_HTTP", "{}"))
    cors = json.loads(os.getenv("CORS_CONFIG", "null")) or http_config.get("cors")
    if cors:
        # Runtime 0.16 的 CorsConfig 未暴露 Starlette 的 allow_private_network。
        # 自定义 app 的 CORS 在 Runtime 的 CORS 之前处理 OPTIONS，仍校验来源白名单。
        cors = {**cors, "allow_private_network": (
            os.getenv("LANGSMITH_LANGGRAPH_API_VARIANT") == "local_dev"
            and os.getenv("ALLOW_PRIVATE_NETWORK", "").lower() == "true"
        )}
    return create_app(container_factory=create_container, cors_options=cors)


def _validate_catalogs() -> None:
    intents = set(INTENT_CATALOG)
    prompts = set(PROMPT_REGISTRY)
    tool_policies = set(TOOL_CATALOG)
    if intents != prompts or intents != tool_policies:
        raise ValueError(
            "Intent、Prompt 和 Tool catalog 的意图集合必须一致。"
        )

    for name, spec in INTENT_CATALOG.items():
        if not spec.criteria.strip() or not PROMPT_REGISTRY[name].system_prompt.strip():
            raise ValueError(f"意图 {name!r} 的 criteria 和 Prompt 不能为空。")
        permissions = TOOL_CATALOG[name].tools
        if len({permission.name for permission in permissions}) != len(permissions):
            raise ValueError(f"意图 {name!r} 的工具权限重复。")
        if any(
            not permission.identity_levels
            or not permission.identity_levels.issubset(frozenset(IdentityLevel))
            for permission in permissions
        ):
            raise ValueError(f"意图 {name!r} 的工具身份权限不能为空或包含未知等级。")
        if spec.response_policy is None:
            if permissions:
                raise ValueError("MVP 普通对话不注册业务工具。")
            continue
        policy = RESPONSE_POLICY_REGISTRY.get(spec.response_policy)
        if policy is None:
            raise ValueError(f"意图 {name!r} 的回答策略 {spec.response_policy!r} 未注册。")
        configured = {permission.name for permission in TOOL_CATALOG[name].tools}
        if not policy.tool_names.issubset(configured):
            raise ValueError(f"意图 {name!r} 的工具配置与回答策略不一致。")

    configured_tools = {
        permission.name
        for spec in TOOL_CATALOG.values()
        for permission in spec.tools
    }
    available_tools = set(TOOL_REGISTRY)
    missing_tools = configured_tools.difference(available_tools)
    if missing_tools:
        raise ValueError(
            f"TOOL_CATALOG 引用了未注册工具："
            f"{', '.join(sorted(missing_tools))}。"
        )
