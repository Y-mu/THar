from __future__ import annotations

import ast
import unittest
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

from langHar.agents.intent_recognition import IntentRecognitionService
from langHar.agents.intent_recognition.recognizer import (
    Intention,
    IntentionRecognitionUnavailable,
    IntentMatch,
)
from langHar.agents.core.chat_message import ChatMessage
from langHar.config import Settings


class FakeIntention(Intention):
    def __init__(self, match: IntentMatch | None = None) -> None:
        self.match = match

    async def classify(
        self,
        current_message: str,
        context: Sequence[ChatMessage],
    ) -> IntentMatch:
        if self.match is None:
            raise IntentionRecognitionUnavailable("test")
        return self.match


def match(intent: str, confidence: float) -> IntentMatch:
    return IntentMatch(
        intent=intent,
        confidence=confidence,
        probabilities={intent: confidence},
        model="fake",
    )


class IntentRecognitionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_known_high_confidence_intent(self) -> None:
        service = IntentRecognitionService(
            FakeIntention(match("weather", 0.9)),
            {"weather"},
        )

        decision = await service.recognize("北京天气", [])

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.target, "weather")
        self.assertEqual(decision.reason, "intent_accepted")

    async def test_rejects_low_confidence_intent(self) -> None:
        service = IntentRecognitionService(
            FakeIntention(match("weather", 0.4)),
            {"weather"},
            confidence_threshold=0.55,
        )

        decision = await service.recognize("可能查天气", [])

        self.assertFalse(decision.accepted)
        self.assertIsNone(decision.target)
        self.assertEqual(decision.reason, "intent_confidence_below_threshold")

    async def test_rejects_unknown_intent(self) -> None:
        service = IntentRecognitionService(
            FakeIntention(match("orders", 0.9)),
            {"weather"},
        )

        decision = await service.recognize("查订单", [])

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "unknown_intent")

    async def test_fails_closed_when_recognition_is_unavailable(self) -> None:
        service = IntentRecognitionService(FakeIntention(), {"weather"})

        decision = await service.recognize("北京天气", [])

        self.assertFalse(decision.accepted)
        self.assertIsNone(decision.target)
        self.assertEqual(decision.reason, "intention_unavailable")
        self.assertIsNone(decision.match.intent)


class IntentRecognitionBoundaryTests(unittest.TestCase):
    def test_agent_service_only_uses_public_intent_service(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        path = project_root / "langHar" / "agents" / "agent_service.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }

        self.assertIn("langHar.agents.intent_recognition", imports)
        self.assertTrue(
            {
                "langHar.agents.intent_recognition.catalog",
                "langHar.agents.intent_recognition.jev",
                "langHar.agents.intent_recognition.recognizer",
                "langHar.agents.intent_recognition.service",
            }.isdisjoint(imports)
        )


class SettingsTests(unittest.TestCase):
    def test_accepts_documented_deepseek_environment_names(self) -> None:
        environment = {
            "DEEPSEEK_API_KEY": "deepseek-key",
            "TYPESAFE_API_KEY": "typesafe-key",
        }
        with (
            patch("langHar.config.load_dotenv"),
            patch.dict("os.environ", environment, clear=True),
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.llm_api_key, "deepseek-key")
        self.assertEqual(settings.llm_model, "deepseek-chat")
        self.assertEqual(settings.jev_model, "jev-latest")


if __name__ == "__main__":
    unittest.main()
