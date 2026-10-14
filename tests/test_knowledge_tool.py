from __future__ import annotations

import json
import unittest
import warnings

from langchain.tools import ToolRuntime

from langHar.capabilities.tools.builtin.knowledge_search import (
    create_knowledge_list_tool, create_knowledge_search_tool,
)
from langHar.core.agent import AgentContext, IdentityLevel
from langHar.core.knowledge import Citation, IndexedDocument, KnowledgeCatalogResult, RetrievalResult


class KnowledgeToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.queries = []
        self.context = AgentContext("knowledge-session", 7, IdentityLevel.L2,
                                    tenant_id="tenant-a", knowledge_base_id="support")

    def runtime(self, context=None):
        return ToolRuntime(
            state={}, context=context or self.context, config={},
            stream_writer=lambda _: None, tool_call_id="call-1", store=None,
        )

    async def test_search_uses_trusted_scope_and_serializes_citations_without_warnings(self):
        async def search(query):
            self.queries.append(query)
            return RetrievalResult(status="ok", citations=(Citation("1", "policy.md", "doc-1", "七天内可退款。"),))

        tool = create_knowledge_search_tool(search)
        self.assertEqual(set(tool.tool_call_schema.model_json_schema()["properties"]), {"query"})
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            output = await tool.ainvoke({"query": "退款规则", "runtime": self.runtime()})
        self.assertEqual(caught, [])
        query = self.queries[0]
        self.assertEqual((query.tenant_id, query.knowledge_base_id, query.user_id, query.identity_level),
                         ("tenant-a", "support", 7, IdentityLevel.L2))
        self.assertEqual(json.loads(output)["citations"][0]["id"], "1")

    async def test_catalog_uses_trusted_scope_and_exposes_only_pagination(self):
        async def catalog(query):
            self.queries.append(query)
            return KnowledgeCatalogResult(status="ok", total=1,
                documents=(IndexedDocument("doc-1", "policy.md", ("v1",), 2),))

        tool = create_knowledge_list_tool(catalog)
        self.assertEqual(set(tool.tool_call_schema.model_json_schema()["properties"]), {"limit", "offset"})
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            output = await tool.ainvoke({"limit": 50, "offset": 0, "runtime": self.runtime()})
        self.assertEqual(caught, [])
        query = self.queries[0]
        self.assertEqual((query.tenant_id, query.knowledge_base_id, query.user_id, query.identity_level),
                         ("tenant-a", "support", 7, IdentityLevel.L2))
        self.assertEqual(json.loads(output)["total"], 1)

    async def test_untrusted_runtime_cannot_reach_search_or_catalog(self):
        async def unexpected_query(query):
            self.fail("untrusted runtime reached retrieval")

        for tool, args in (
            (create_knowledge_search_tool(unexpected_query), {"query": "规则"}),
            (create_knowledge_list_tool(unexpected_query), {}),
        ):
            with self.assertRaisesRegex(PermissionError, "缺少可信 AgentContext"):
                await tool.ainvoke({**args, "runtime": self.runtime({"user_id": 0, "identity_level": "admin"})})


if __name__ == "__main__":
    unittest.main()
