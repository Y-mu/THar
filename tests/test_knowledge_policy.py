from __future__ import annotations

import unittest

from langHar.capabilities.knowledge.policy import (
    KnowledgeResponsePolicy, KNOWLEDGE_EMPTY_CATALOG_MESSAGE,
    KNOWLEDGE_NO_EVIDENCE_MESSAGE, KNOWLEDGE_UNAVAILABLE_MESSAGE,
)
from langHar.core.knowledge import (
    Citation, IndexedDocument, KnowledgeCatalogResult, KnowledgeToolResult, RetrievalResult,
)


class KnowledgePolicyTests(unittest.TestCase):
    """Business rules tested without LangChain graphs, SDK mocks or any I/O."""

    def setUp(self):
        self.policy = KnowledgeResponsePolicy()
        self.evidence = KnowledgeToolResult("knowledge_search", RetrievalResult(
            status="ok", citations=(Citation("1", "policy.md", "doc-1", "七天内可退款。"),),
        ))

    def test_first_call_can_proceed_but_answer_without_tools_is_rejected(self):
        self.assertIsNone(self.policy.after_tools([]))
        self.assertEqual(self.policy.after_answer("猜测 [1]", []).content, KNOWLEDGE_NO_EVIDENCE_MESSAGE)

    def test_valid_evidence_allows_generation_and_real_citations(self):
        self.assertIsNone(self.policy.after_tools([self.evidence]))
        decision = self.policy.after_answer("七天内可退款 [1]。", [self.evidence])
        self.assertTrue(decision.accepted)
        self.assertIsNone(decision.reason)

    def test_missing_and_forged_citations_are_rejected(self):
        for answer in ("七天内可退款。", "七天内可退款 [99]。", "七天内可退款 [1]、[99]。"):
            self.assertFalse(self.policy.after_answer(answer, [self.evidence]).accepted)

    def test_failure_dominates_success(self):
        failure = KnowledgeToolResult("knowledge_search", failed=True)
        decision = self.policy.after_tools([failure, self.evidence])
        self.assertEqual(decision.content, KNOWLEDGE_UNAVAILABLE_MESSAGE)
        self.assertFalse(decision.accepted)

    def test_empty_catalog_is_authoritative_absence_not_a_service_failure(self):
        decision = self.policy.after_tools([KnowledgeToolResult(
            "knowledge_list_documents", KnowledgeCatalogResult(status="empty"),
        )])
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.content, KNOWLEDGE_EMPTY_CATALOG_MESSAGE)

    def test_filename_is_escaped_and_never_treated_as_instructions_or_content(self):
        decision = self.policy.after_tools([KnowledgeToolResult(
            "knowledge_list_documents", KnowledgeCatalogResult(
                status="ok", total=1,
                documents=(IndexedDocument("doc", "[点击](javascript:alert(1))<script>\n.md", ("v1",), 2),),
            ),
        )])
        self.assertTrue(decision.accepted)
        self.assertNotIn("<script>", decision.content)
        self.assertNotIn("[点击](", decision.content)
        self.assertIn("不代表正文内容摘要", decision.content)

    def test_invalid_tool_payload_type_cannot_supply_evidence(self):
        invalid = KnowledgeToolResult("knowledge_list_documents", self.evidence.payload)
        self.assertFalse(self.policy.after_tools([invalid]).accepted)

    def test_policy_does_not_remember_previous_calls(self):
        self.assertTrue(self.policy.after_answer("退款 [1]。", [self.evidence]).accepted)
        self.assertFalse(self.policy.after_answer("退款 [1]。", []).accepted)


if __name__ == "__main__":
    unittest.main()
