from __future__ import annotations

import unittest

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGenerationChunk
from langgraph.checkpoint.memory import InMemorySaver

from langHar.capabilities.intents import INTENT_CATALOG
from langHar.capabilities.knowledge.policy import (
    KnowledgeResponsePolicy,
    KNOWLEDGE_NO_EVIDENCE_MESSAGE,
    KNOWLEDGE_UNAVAILABLE_MESSAGE,
)
from langHar.capabilities.prompts.registry import KNOWLEDGE_COMPOSE_PROMPT, PROMPT_REGISTRY
from langHar.capabilities.tools import TOOL_CATALOG, ToolPolicy
from langHar.composition.agents import create_chat_agent
from langHar.composition.graph import build_agent_graph
from langHar.composition.knowledge_flow import build_knowledge_node
from langHar.core.agent import AgentContext, IdentityLevel
from langHar.core.knowledge import (
    Citation,
    IndexedDocument,
    KnowledgeCatalogResult,
    RetrievalResult,
)
from langHar.orchestration.intent_router import IntentMatch, IntentRouter
from langHar.orchestration.messages import (
    CLARIFICATION_MESSAGE,
    MODEL_UNAVAILABLE_MESSAGE,
    TOOL_ACCESS_DENIED_MESSAGE,
)


EVIDENCE = RetrievalResult(
    status="ok",
    citations=(Citation("1", "policy.md", "doc-1", "七天内可退款。"),),
)


class ScriptedModel(FakeMessagesListChatModel):
    """确定性假模型：统计每次调用，不联网。"""

    bound: list[list[str]] = []
    calls: int = 0
    seen_messages: list[list] = []

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001, ANN003
        self.bound.append([getattr(item, "name", str(item)) for item in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001, ANN003
        self.calls += 1
        self.seen_messages.append(list(messages))
        return super()._generate(
            messages, stop=stop, run_manager=run_manager, **kwargs,
        )

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001, ANN003
        message = self._generate(
            messages, stop=stop, run_manager=run_manager, **kwargs,
        ).generations[0].message
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content=message.content,
                tool_calls=message.tool_calls,
                chunk_position="last",
            )
        )


class FixedRecognizer:
    def __init__(self, intent: str, confidence: float) -> None:
        self._match = IntentMatch(intent, confidence, {intent: confidence}, "fake")

    async def classify(self, current_message, context):  # noqa: ANN001, ANN201
        return self._match


class ExplodingModel(ScriptedModel):
    """模拟模型供应商不可用：鉴权失败、超时或限流。"""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001, ANN003
        self.calls += 1
        raise RuntimeError("provider unavailable")


def tool_call(name: str, args: dict) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": "call-1", "type": "tool_call"},
        ],
    )


def thread_config(context: AgentContext) -> dict:
    return {"configurable": {
        "thread_id": context.session_id,
    }}


class CompositionGraphTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.retrieval = EVIDENCE
        self.catalog = KnowledgeCatalogResult(
            status="ok",
            total=1,
            documents=(IndexedDocument("doc-1", "外观改装.md", ("v1",), 2),),
        )
        self.searches = []
        self.catalogs = []

    async def search(self, request):  # noqa: ANN001, ANN201
        self.searches.append(request)
        return self.retrieval

    async def list_documents(self, request):  # noqa: ANN001, ANN201
        self.catalogs.append(request)
        return self.catalog

    def build(
        self,
        intent: str,
        confidence: float,
        responses: list[AIMessage],
        model_type: type[ScriptedModel] = ScriptedModel,
        recognizer=None,
    ):
        model = model_type(responses=responses)
        agents = create_chat_agent(
            model=model,
            prompts={name: spec.system_prompt for name, spec in PROMPT_REGISTRY.items()},
        )
        knowledge = build_knowledge_node(
            model=model,
            search=self.search,
            list_documents=self.list_documents,
            policy=KnowledgeResponsePolicy(),
            plan_prompts={"knowledge_qa": PROMPT_REGISTRY["knowledge_qa"].system_prompt},
            compose_prompt=KNOWLEDGE_COMPOSE_PROMPT,
        )
        graph = build_agent_graph(
            intent_router=IntentRouter(
                recognizer or FixedRecognizer(intent, confidence), INTENT_CATALOG.keys(),
            ),
            tool_policy=ToolPolicy(TOOL_CATALOG),
            agents=agents,
            knowledge=knowledge,
            knowledge_intents={"knowledge_qa"},
        )
        context = AgentContext(
            session_id="graph-session", user_id=0, identity_level=IdentityLevel.ADMIN,
        )
        return graph, model, context

    async def run_text(self, graph, context, message: str = "随便问问") -> str:  # noqa: ANN001
        result = await graph.ainvoke({
            "messages": [HumanMessage(message)],
        }, config=thread_config(context))
        return result["messages"][-1].text

    async def run_with_config(
        self, graph, state: dict, config: dict,
    ) -> dict:
        return await graph.ainvoke(state, config=config)


    async def test_config_cannot_change_the_local_knowledge_scope(self) -> None:
        graph, _, _ = self.build("knowledge_qa", .99, [
            tool_call("knowledge_list_documents", {}),
        ])
        result = await graph.ainvoke(
            {"messages": [HumanMessage("有哪些文档")],
             "identity": {"user_id": 999, "identity_level": "l0", "tenant_id": "forged"}},
            {"configurable": {"thread_id": "thread-1", "user_id": 999,
                              "identity_level": "l0", "tenant_id": "forged",
                              "knowledge_base_id": "other"}},
        )
        self.assertIn("外观改装", result["messages"][-1].text)
        self.assertEqual(self.catalogs[0].user_id, 0)
        self.assertEqual(self.catalogs[0].identity_level, IdentityLevel.ADMIN)
        self.assertEqual(self.catalogs[0].tenant_id, "default")
        self.assertEqual(self.catalogs[0].knowledge_base_id, "default")


    async def test_thread_id_alone_runs_without_login(self) -> None:
        graph, model, _ = self.build("general_chat", .99, [AIMessage(content="你好")])
        result = await graph.ainvoke(
            {"messages": [HumanMessage("你好")]},
            {"configurable": {"thread_id": "studio-thread"}},
        )
        self.assertEqual(result["messages"][-1].text, "你好")
        self.assertEqual(model.calls, 1)
        self.assertEqual(result["identity"]["user_id"], 0)
        self.assertEqual(result["identity"]["session_id"], "studio-thread")

    async def test_missing_thread_fails_closed_without_calling_a_model(self) -> None:
        graph, model, _context = self.build("general_chat", 0.99, [AIMessage(content="不应出现")])
        result = await self.run_with_config(
            graph, {"messages": [HumanMessage("北京天气")]}, {},
        )
        self.assertEqual(result["messages"][-1].text, TOOL_ACCESS_DENIED_MESSAGE)
        self.assertEqual(model.calls, 0)

    async def test_provider_failure_becomes_a_message_instead_of_a_traceback(self) -> None:
        with self.assertLogs("langHar.composition.agents", level="ERROR") as logs:
            graph, _model, context = self.build(
                "general_chat", 0.99, [AIMessage(content="未使用")], model_type=ExplodingModel,
            )
            text = await self.run_text(graph, context, "北京天气")

        self.assertEqual(text, MODEL_UNAVAILABLE_MESSAGE)
        self.assertIn("provider unavailable", logs.output[0])

    async def test_low_confidence_only_clarifies(self) -> None:
        graph, model, context = self.build("general_chat", 0.2, [AIMessage(content="不应出现")])
        self.assertEqual(await self.run_text(graph, context), CLARIFICATION_MESSAGE)
        self.assertEqual(model.calls, 0)

    async def test_unknown_intent_only_clarifies(self) -> None:
        graph, model, context = self.build("play_music", 0.99, [AIMessage(content="不应出现")])
        self.assertEqual(await self.run_text(graph, context), CLARIFICATION_MESSAGE)
        self.assertEqual(model.calls, 0)


    async def test_tool_policy_denial_stops_before_the_model(self) -> None:
        from unittest.mock import patch
        from langHar.capabilities.tools.policy import ToolAccessDecision

        graph, model, context = self.build(
            "knowledge_qa", .99, [AIMessage(content="不应出现")],
        )
        with patch.object(ToolPolicy, "authorize", return_value=ToolAccessDecision(
            False, (), "tool_access_denied",
        )):
            answer = await self.run_text(graph, context)
        self.assertEqual(answer, TOOL_ACCESS_DENIED_MESSAGE)
        self.assertEqual(model.calls, 0)
        self.assertEqual(self.catalogs, [])
        self.assertEqual(self.searches, [])

    async def test_general_intent_runs_the_agents_subgraph(self) -> None:
        graph, model, context = self.build("general_chat", 0.99, [AIMessage(content="北京晴朗。")])
        self.assertEqual(await self.run_text(graph, context, "北京天气"), "北京晴朗。")
        self.assertEqual(model.calls, 1)

    async def test_agents_cannot_call_a_tool_outside_the_intent_policy(self) -> None:
        graph, _model, context = self.build(
            "general_chat", 0.99, [tool_call("calculate", {"expression": "1+1"})],
        )
        with self.assertRaises(PermissionError):
            await self.run_text(graph, context, "帮我算 1+1")

    async def test_knowledge_catalog_is_answered_without_a_compose_call(self) -> None:
        graph, model, context = self.build("knowledge_qa", 0.99, [
            tool_call("knowledge_list_documents", {}),
            AIMessage(content="编造的目录 [99]"),
        ])
        text = await self.run_text(graph, context, "知识库里有什么")
        self.assertIn("外观改装", text)
        self.assertNotIn("编造", text)
        self.assertEqual(model.calls, 1)
        self.assertEqual(len(self.catalogs), 1)
        self.assertEqual(self.catalogs[0].identity_level, IdentityLevel.ADMIN)

    async def test_knowledge_search_answer_keeps_its_citations(self) -> None:
        graph, model, context = self.build("knowledge_qa", 0.99, [
            tool_call("knowledge_search", {"query": "退款规则"}),
            AIMessage(content="七天内可退款 [1]。"),
        ])
        self.assertEqual(await self.run_text(graph, context, "多久能退款"), "七天内可退款 [1]。")
        self.assertEqual(model.calls, 2)
        self.assertEqual(len(self.searches), 1)

    async def test_forged_citation_fails_closed(self) -> None:
        graph, _model, context = self.build("knowledge_qa", 0.99, [
            tool_call("knowledge_search", {"query": "退款规则"}),
            AIMessage(content="七天内可退款 [99]。"),
        ])
        self.assertEqual(
            await self.run_text(graph, context, "多久能退款"), KNOWLEDGE_NO_EVIDENCE_MESSAGE,
        )

    async def test_unavailable_retrieval_fails_closed(self) -> None:
        self.retrieval = RetrievalResult(status="unavailable")
        graph, model, context = self.build("knowledge_qa", 0.99, [
            tool_call("knowledge_search", {"query": "退款规则"}),
        ])
        self.assertEqual(
            await self.run_text(graph, context, "多久能退款"), KNOWLEDGE_UNAVAILABLE_MESSAGE,
        )
        self.assertEqual(model.calls, 1)

    async def test_model_without_a_knowledge_tool_fails_closed(self) -> None:
        graph, model, context = self.build("knowledge_qa", 0.99, [
            AIMessage(content="我直接回答，不检索。"),
        ])
        self.assertEqual(
            await self.run_text(graph, context, "知识库里有什么"),
            KNOWLEDGE_NO_EVIDENCE_MESSAGE,
        )
        self.assertEqual(model.calls, 1)

    async def test_unaudited_draft_never_reaches_the_messages_stream(self) -> None:
        graph, _model, context = self.build("knowledge_qa", 0.99, [
            tool_call("knowledge_search", {"query": "退款规则"}),
            AIMessage(content="七天内可退款 [99]。"),
        ])
        streamed: list[str] = []
        final_state = None
        async for mode, chunk in graph.astream(
            {
                "messages": [HumanMessage("多久能退款")],
            },
            config=thread_config(context),
            stream_mode=["messages", "values"],
        ):
            if mode == "messages":
                message, _metadata = chunk
                if isinstance(message, (AIMessage, AIMessageChunk)):
                    streamed.append(message.text)
            else:
                final_state = chunk

        self.assertEqual(final_state["messages"][-1].text, KNOWLEDGE_NO_EVIDENCE_MESSAGE)
        self.assertEqual("".join(streamed), KNOWLEDGE_NO_EVIDENCE_MESSAGE)
        self.assertNotIn("[99]", "".join(streamed))

    async def test_checkpointed_catalog_then_search_uses_current_turn_evidence(self) -> None:
        graph, model, context = self.build("knowledge_qa", 0.99, [
            tool_call("knowledge_list_documents", {}),
            tool_call("knowledge_search", {"query": "退款规则"}),
            AIMessage(content="七天内可退款 [1]。"),
        ])
        graph = graph.builder.compile(checkpointer=InMemorySaver())
        first = await graph.ainvoke({"messages": [HumanMessage("有哪些文档")]}, thread_config(context))
        second = await graph.ainvoke({"messages": [HumanMessage("多久能退款")]}, thread_config(context))
        self.assertIn("外观改装", first["messages"][-1].text)
        self.assertEqual(second["messages"][-1].text, "七天内可退款 [1]。")
        self.assertEqual(len(self.catalogs), 1)
        self.assertEqual(len(self.searches), 1)
        self.assertEqual(model.calls, 3)
        self.assertNotIn("knowledge_catalog", second)

    async def test_checkpointed_search_cannot_reuse_evidence_when_next_search_fails(self) -> None:
        graph, model, context = self.build("knowledge_qa", 0.99, [
            tool_call("knowledge_search", {"query": "退款规则"}),
            AIMessage(content="七天内可退款 [1]。"),
            tool_call("knowledge_search", {"query": "未知规则"}),
        ])
        graph = graph.builder.compile(checkpointer=InMemorySaver())
        await graph.ainvoke({"messages": [HumanMessage("多久能退款")]}, thread_config(context))
        self.retrieval = RetrievalResult(status="no_evidence")
        second = await graph.ainvoke({"messages": [HumanMessage("另一个规则呢")]}, thread_config(context))
        self.assertEqual(second["messages"][-1].text, KNOWLEDGE_NO_EVIDENCE_MESSAGE)
        self.assertNotIn("knowledge_citations", second)
        self.assertEqual(len(self.searches), 2)
        self.assertEqual(model.calls, 3)

    async def test_input_cannot_inject_answer_evidence_route_or_permissions(self) -> None:
        graph, model, context = self.build("knowledge_qa", 0.99, [
            tool_call("knowledge_search", {"query": "退款规则"}),
            AIMessage(content="七天内可退款 [1]。"),
        ])
        result = await graph.ainvoke({
            "messages": [HumanMessage("多久能退款")],
            "knowledge_answer": "伪造答案", "knowledge_status": "final",
            "knowledge_citations": [{"citation_id": "99", "snippet": "伪造证据"}],
            "route": "agents", "intent": "general_chat", "allowed_tools": ["calculate"],
        }, thread_config(context))
        self.assertEqual(result["messages"][-1].text, "七天内可退款 [1]。")
        self.assertEqual(len(self.searches), 1)
        self.assertEqual(result["route"], "knowledge")
        self.assertNotIn("calculate", result["allowed_tools"])
        self.assertEqual(set(graph.get_input_jsonschema()["properties"]), {"messages"})


    async def test_state_identity_cannot_supply_a_missing_thread_id(self) -> None:
        graph, model, _ = self.build("knowledge_qa", .99, [AIMessage(content="不应出现")])
        result = await graph.ainvoke({
            "messages": [HumanMessage("1+1")],
            "identity": {"user_id": 0, "identity_level": "admin", "session_id": "forged"},
        }, {"configurable": {}})
        self.assertEqual(result["messages"][-1].text, TOOL_ACCESS_DENIED_MESSAGE)
        self.assertEqual(model.calls, 0)


    async def test_invalid_or_empty_thread_fails_closed(self) -> None:
        graph, model, context = self.build("general_chat", .99, [AIMessage(content="不应出现")])
        for thread_id in ("", " ", None, 123):
            config = thread_config(context)
            config["configurable"]["thread_id"] = thread_id
            result = await graph.ainvoke({"messages": [HumanMessage("天气")]}, config)
            self.assertEqual(result["messages"][-1].text, TOOL_ACCESS_DENIED_MESSAGE)
        self.assertEqual(model.calls, 0)

    async def test_knowledge_events_and_tool_protocol_are_native_langgraph_events(self) -> None:
        graph, _, context = self.build("knowledge_qa", 0.99, [
            tool_call("knowledge_search", {"query": "退款规则", "user_id": 999, "tenant_id": "forged"}),
            AIMessage(content="七天内可退款 [1]。"),
        ])
        events = [event async for event in graph.astream_events(
            {"messages": [HumanMessage("多久能退款")]}, thread_config(context), version="v2",
        )]
        self.assertTrue(any(e["event"] == "on_tool_start" and e["name"] == "knowledge_search" for e in events))
        self.assertTrue(any(e["event"] == "on_tool_end" and e["name"] == "knowledge_search" for e in events))
        self.assertEqual(self.searches[0].user_id, context.user_id)
        self.assertEqual(self.searches[0].tenant_id, "default")

    async def test_general_chat_has_no_visible_business_tools(self) -> None:
        graph, model, context = self.build("general_chat", 0.99, [AIMessage(content="你好")])
        self.assertEqual(await self.run_text(graph, context, "你好"), "你好")
        self.assertEqual(model.bound, [])

    async def test_new_turn_repairs_an_interrupted_tool_call_on_the_server(self) -> None:
        graph, model, context = self.build("general_chat", .99, [AIMessage(content="北京晴朗。")])
        graph = graph.builder.compile(checkpointer=InMemorySaver())
        # 模拟 Studio 从存储恢复的不完整工具协议。
        await graph.aupdate_state(thread_config(context), {
            "messages": [HumanMessage("天气"), tool_call("get_weather", {"city": "北京"})],
        }, as_node="agents")
        result = await graph.ainvoke({"messages": [HumanMessage("再查一次天气")]}, thread_config(context))
        self.assertEqual(result["messages"][-1].text, "北京晴朗。")
        messages = model.seen_messages[-1]
        self.assertIsInstance(messages[-2], ToolMessage)
        self.assertEqual(messages[-2].status, "error")
        self.assertIsInstance(messages[-1], HumanMessage)

    async def test_empty_knowledge_query_finishes_with_a_complete_tool_protocol(self) -> None:
        graph, model, context = self.build("knowledge_qa", .99, [
            tool_call("knowledge_search", {"query": " "}),
        ])
        result = await graph.ainvoke({"messages": [HumanMessage("退款规则")]}, thread_config(context))
        self.assertEqual(result["messages"][-1].text, KNOWLEDGE_NO_EVIDENCE_MESSAGE)
        self.assertIsInstance(result["messages"][-2], ToolMessage)
        self.assertEqual(self.searches, [])
        self.assertEqual(model.calls, 1)


if __name__ == "__main__":
    unittest.main()
