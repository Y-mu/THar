from __future__ import annotations

import asyncio
import unittest

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langHar.core.agent import AgentContext, IdentityLevel
from langHar.orchestration.intent_router import IntentMatch

from langHar.capabilities.knowledge.policy import KNOWLEDGE_NO_EVIDENCE_MESSAGE, KNOWLEDGE_UNAVAILABLE_MESSAGE
from tests import test_composition_graph as fixtures


class KnowledgeGateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.case = fixtures.CompositionGraphTests()
        self.case.setUp()

    async def test_missing_citations_are_rejected_before_publishing_an_answer(self) -> None:
        graph, model, context = self.case.build("knowledge_qa", .99, [
            fixtures.tool_call("knowledge_search", {"query": "退款规则"}),
            AIMessage(content="七天内可退款。"),
        ])
        self.assertEqual(await self.case.run_text(graph, context), KNOWLEDGE_NO_EVIDENCE_MESSAGE)
        self.assertEqual(model.calls, 2)

    async def test_plan_failure_does_not_retrieve_or_leak_a_traceback(self) -> None:
        graph, model, context = self.case.build("knowledge_qa", .99,
            [AIMessage(content="未使用")], model_type=fixtures.ExplodingModel)
        with self.assertLogs("langHar.composition.knowledge_flow", level="ERROR"):
            answer = await self.case.run_text(graph, context)
        self.assertEqual(answer, KNOWLEDGE_UNAVAILABLE_MESSAGE)
        self.assertEqual(model.calls, 1)
        self.assertEqual(self.case.searches, [])

    async def test_retrieval_exception_stops_before_composition(self) -> None:
        async def failing_search(query):
            raise RuntimeError("private backend details")
        self.case.search = failing_search
        graph, model, context = self.case.build("knowledge_qa", .99, [
            fixtures.tool_call("knowledge_search", {"query": "规则"}),
            AIMessage(content="不应调用"),
        ])
        with self.assertLogs("langHar.composition.knowledge_flow", level="ERROR"):
            answer = await self.case.run_text(graph, context)
        self.assertEqual(answer, KNOWLEDGE_UNAVAILABLE_MESSAGE)
        self.assertEqual(model.calls, 1)

    async def test_unauthorized_or_multiple_planned_tools_fail_closed(self) -> None:
        for response in (
            fixtures.tool_call("calculate", {"expression": "1+1"}),
            AIMessage(content="", tool_calls=[
                {"name": "knowledge_search", "args": {"query": "规则"}, "id": "a", "type": "tool_call"},
                {"name": "knowledge_list_documents", "args": {}, "id": "b", "type": "tool_call"},
            ]),
        ):
            graph, model, context = self.case.build("knowledge_qa", .99, [response])
            self.assertEqual(await self.case.run_text(graph, context), KNOWLEDGE_NO_EVIDENCE_MESSAGE)
            self.assertEqual(model.calls, 1)
        self.assertEqual(self.case.searches, [])
        self.assertEqual(self.case.catalogs, [])

    async def test_planner_draft_is_absent_from_stream_and_checkpoint_messages(self) -> None:
        response = fixtures.tool_call("knowledge_search", {"query": "退款规则"})
        response.content = "未经审计的计划草稿"
        graph, _, context = self.case.build("knowledge_qa", .99, [response, AIMessage(content="七天内可退款 [1]。")])
        streamed = []
        final = None
        async for mode, chunk in graph.astream(
            {"messages": [HumanMessage("退款规则")]}, fixtures.thread_config(context),
            stream_mode=["messages", "values"],
        ):
            if mode == "messages":
                streamed.append(chunk[0].text)
            else:
                final = chunk
        self.assertNotIn("未经审计", "".join(streamed))
        self.assertNotIn("未经审计", "".join(message.text for message in final["messages"]))
        self.assertEqual(final["messages"][-1].text, "七天内可退款 [1]。")

    async def test_unaudited_answer_never_enters_subgraph_values_or_checkpoints(self) -> None:
        from langgraph.checkpoint.memory import InMemorySaver
        graph, _, context = self.case.build("knowledge_qa", .99, [
            fixtures.tool_call("knowledge_search", {"query": "退款规则"}),
            AIMessage(content="未经审计的伪造结论 [99]。"),
        ])
        graph = graph.builder.compile(checkpointer=InMemorySaver())
        states = []
        async for namespace, state in graph.astream(
            {"messages": [HumanMessage("退款规则")]}, fixtures.thread_config(context),
            stream_mode="values", subgraphs=True,
        ):
            states.append(state)
        self.assertTrue(states)
        for state in states:
            self.assertNotIn("未经审计", state.get("knowledge_answer", ""))
            self.assertNotIn("未经审计", "".join(message.text for message in state.get("messages", ())))
        async for checkpoint in graph.aget_state_history(fixtures.thread_config(context)):
            self.assertNotIn("未经审计", checkpoint.values.get("knowledge_answer", ""))

    async def test_concurrent_threads_share_the_graph_without_sharing_route_or_evidence(self) -> None:
        from langgraph.checkpoint.memory import InMemorySaver

        class PromptModel(fixtures.ScriptedModel):
            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                self.calls += 1
                self.seen_messages.append(list(messages))
                if "友好的中文助手" in messages[0].text:
                    response = AIMessage(content="北京晴朗。")
                else:
                    response = fixtures.tool_call("knowledge_list_documents", {})
                return ChatResult(generations=[ChatGeneration(message=response)])

        class Recognizer:
            async def classify(self, message, history):
                intent = "knowledge_qa" if "知识库" in message else "general_chat"
                return IntentMatch(intent, .99, {intent: .99}, "fake")

        graph, model, _ = self.case.build("general_chat", .99, [AIMessage(content="未使用")],
                                         model_type=PromptModel, recognizer=Recognizer())
        graph = graph.builder.compile(checkpointer=InMemorySaver())
        weather, knowledge = await asyncio.gather(
            graph.ainvoke({"messages": [HumanMessage("北京天气")]}, fixtures.thread_config(
                AgentContext("weather-thread", 7, IdentityLevel.L2))),
            graph.ainvoke({"messages": [HumanMessage("知识库里有什么")]}, fixtures.thread_config(
                AgentContext("knowledge-thread", 0, IdentityLevel.ADMIN))),
        )
        self.assertEqual(weather["messages"][-1].text, "北京晴朗。")
        self.assertEqual(weather["intent"], "general_chat")
        self.assertEqual(weather["allowed_tools"], [])
        self.assertNotIn("knowledge_catalog", weather)
        self.assertIn("外观改装", knowledge["messages"][-1].text)
        self.assertEqual(knowledge["intent"], "knowledge_qa")
        self.assertEqual(self.case.catalogs[0].user_id, 0)
        self.assertEqual(model.calls, 2)


if __name__ == "__main__":
    unittest.main()
