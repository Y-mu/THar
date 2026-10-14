from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from langchain_core.messages import AIMessage

from langHar.bootstrap import create_agent_graph, create_container
from langHar.capabilities.intents import INTENT_CATALOG
from langHar.capabilities.prompts import PROMPT_REGISTRY
from langHar.capabilities.tools import TOOL_CATALOG
from langHar.config import Settings
from tests import test_composition_graph as fixtures


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(llm_api_key="test", typesafe_api_key="test")

    def test_builds_one_public_graph_without_an_embedded_checkpointer(self) -> None:
        model = fixtures.ScriptedModel(responses=[AIMessage(content="未使用")])
        with patch("langHar.bootstrap.create_chat_model", return_value=model) as create:
            graph = create_agent_graph(self.settings)
        create.assert_called_once()
        self.assertEqual(set(graph.nodes), {"__start__", "route_intent", "agents", "knowledge", "clarify", "denied"})
        self.assertIsNone(graph.checkpointer)
        self.assertEqual(set(graph.get_input_jsonschema()["properties"]), {"messages"})

    def assert_startup_rejected(self, patch_name, catalog, message):
        with patch(patch_name, catalog), patch("langHar.bootstrap.create_chat_model") as create:
            with self.assertRaisesRegex(ValueError, message):
                create_agent_graph(self.settings)
            create.assert_not_called()

    def test_unknown_response_policy_rejects_startup(self) -> None:
        catalog = dict(INTENT_CATALOG)
        catalog["knowledge_qa"] = replace(catalog["knowledge_qa"], response_policy="missing")
        self.assert_startup_rejected("langHar.bootstrap.INTENT_CATALOG", catalog, "回答策略.*未注册")

    def test_response_policy_and_tool_catalog_mismatch_rejects_startup(self) -> None:
        catalog = dict(TOOL_CATALOG)
        catalog["knowledge_qa"] = replace(catalog["knowledge_qa"], tools=())
        self.assert_startup_rejected("langHar.bootstrap.TOOL_CATALOG", catalog, "工具配置与回答策略不一致")

    def test_missing_prompt_rejects_startup(self) -> None:
        catalog = dict(PROMPT_REGISTRY)
        catalog.pop("general_chat")
        self.assert_startup_rejected("langHar.bootstrap.PROMPT_REGISTRY", catalog, "意图集合必须一致")

    def test_unregistered_tool_rejects_startup(self) -> None:
        catalog = dict(TOOL_CATALOG)
        permission = replace(catalog["knowledge_qa"].tools[0], name="missing_tool")
        catalog["knowledge_qa"] = replace(catalog["knowledge_qa"], tools=(*catalog["knowledge_qa"].tools, permission))
        self.assert_startup_rejected("langHar.bootstrap.TOOL_CATALOG", catalog, "未注册工具")

    def test_empty_identity_permissions_reject_startup(self) -> None:
        catalog = dict(TOOL_CATALOG)
        permission = replace(catalog["knowledge_qa"].tools[0], identity_levels=frozenset())
        catalog["knowledge_qa"] = replace(catalog["knowledge_qa"], tools=(permission,))
        self.assert_startup_rejected("langHar.bootstrap.TOOL_CATALOG", catalog, "身份权限不能为空")

    def test_renamed_knowledge_intent_is_routed_from_catalog(self) -> None:
        intents, prompts, tools = dict(INTENT_CATALOG), dict(PROMPT_REGISTRY), dict(TOOL_CATALOG)
        for catalog in (intents, prompts, tools):
            catalog["document_qa"] = catalog.pop("knowledge_qa")
        with (
            patch("langHar.bootstrap.INTENT_CATALOG", intents),
            patch("langHar.bootstrap.PROMPT_REGISTRY", prompts),
            patch("langHar.bootstrap.TOOL_CATALOG", tools),
            patch("langHar.bootstrap.create_chat_model", return_value=fixtures.ScriptedModel(responses=[AIMessage(content="未使用")])),
            patch("langHar.bootstrap.build_agent_graph", return_value=object()) as build,
        ):
            create_agent_graph(self.settings)
        self.assertEqual(build.call_args.kwargs["knowledge_intents"], {"document_qa"})

    def test_http_container_does_not_construct_an_agent_or_model(self) -> None:
        with patch("langHar.bootstrap.create_chat_model") as create:
            container = create_container()
        create.assert_not_called()
        self.assertFalse(hasattr(container, "auth_service"))
        self.assertIsNotNone(container.knowledge_ingestion)
        self.assertFalse(hasattr(container, "chat_service"))


if __name__ == "__main__":
    unittest.main()
