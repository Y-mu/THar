from __future__ import annotations

import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
        elif isinstance(node, ast.Import):
            modules.update(name.name for name in node.names)
    return modules


def python_files(relative: str) -> list[Path]:
    return list((PROJECT_ROOT / relative).rglob("*.py"))


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_only_langgraph_owns_chat_and_session_execution(self) -> None:
        for relative in (
            "langHar/orchestration/agent_service.py", "langHar/orchestration/agent_executor.py",
            "langHar/infrastructure/llm/langchain_agent.py", "langHar/infrastructure/llm/knowledge_middleware.py",
        ):
            self.assertFalse((PROJECT_ROOT / relative).exists())
        for module in ("chat", "session"):
            self.assertEqual(list((PROJECT_ROOT / "langHar/api" / module).glob("*.py")), [])
        import json
        config = json.loads((PROJECT_ROOT / "langgraph.json").read_text())
        self.assertEqual(config["graphs"], {"agent": "./langHar/graph_entry.py:graph"})
        self.assertNotIn("auth", config)
        self.assertFalse((PROJECT_ROOT / "langHar/api/langgraph_auth.py").exists())

    def test_knowledge_response_policy_is_framework_independent(self) -> None:
        forbidden = (
            "langHar.api", "langHar.infrastructure", "langHar.orchestration",
            "langchain", "langgraph", "fastapi", "pydantic",
        )
        path = PROJECT_ROOT / "langHar/capabilities/knowledge/policy.py"
        self.assertFalse(any(module.startswith(forbidden) for module in imported_modules(path)))

    def test_api_uses_business_modules_without_global_routes_or_schemas(self) -> None:
        api_root = PROJECT_ROOT / "langHar" / "api"
        self.assertFalse((api_root / "routes").exists())
        self.assertFalse((PROJECT_ROOT / "langHar" / "schemas").exists())
        for module in ("knowledge",):
            self.assertTrue((api_root / module / "route.py").is_file())
            self.assertTrue((api_root / module / "schemas.py").is_file())

    def test_api_does_not_import_agent_implementations(self) -> None:
        forbidden = (
            "langHar.bootstrap",
            "langHar.composition",
            "langHar.capabilities",
            "langHar.infrastructure",
            "langHar.orchestration",
        )
        violations = [
            str(path.relative_to(PROJECT_ROOT))
            for path in python_files("langHar/api")
            if any(
                module.startswith(forbidden)
                for module in imported_modules(path)
            )
        ]
        self.assertEqual(violations, [])

    def test_agent_layers_do_not_import_api(self) -> None:
        violations = [
            str(path.relative_to(PROJECT_ROOT))
            for relative in (
                "langHar/orchestration",
                "langHar/capabilities",
                "langHar/infrastructure",
            )
            for path in python_files(relative)
            if any(
                module.startswith("langHar.api")
                for module in imported_modules(path)
            )
        ]
        self.assertEqual(violations, [])

    def test_orchestration_does_not_import_infrastructure_or_ai_frameworks(self) -> None:
        forbidden = (
            "langHar.infrastructure",
            "langHar.composition",
            "fastapi",
            "pydantic",
            "langchain",
            "langgraph",
            "langchain_openai",
            "typesafe_sdk",
        )
        violations = [
            str(path.relative_to(PROJECT_ROOT))
            for path in python_files("langHar/orchestration")
            if any(
                module.startswith(forbidden)
                for module in imported_modules(path)
            )
        ]
        self.assertEqual(violations, [])

    def test_core_is_framework_independent(self) -> None:
        forbidden = (
            "langHar.api",
            "langHar.orchestration",
            "langHar.capabilities",
            "langHar.infrastructure",
            "langHar.composition",
            "fastapi",
            "pydantic",
            "langchain",
            "langgraph",
            "typesafe_sdk",
        )
        violations = [
            str(path.relative_to(PROJECT_ROOT))
            for path in python_files("langHar/core")
            if any(
                module.startswith(forbidden)
                for module in imported_modules(path)
            )
        ]
        self.assertEqual(violations, [])

    def test_only_bootstrap_wires_infrastructure_into_graphs(self) -> None:
        violations: list[str] = []
        for path in python_files("langHar"):
            relative = path.relative_to(PROJECT_ROOT)
            if (
                relative == Path("langHar/bootstrap.py")
                or "infrastructure" in relative.parts
            ):
                continue
            modules = imported_modules(path)
            has_orchestration = any(
                module.startswith("langHar.orchestration") for module in modules
            )
            has_infrastructure = any(
                module.startswith("langHar.infrastructure") for module in modules
            )
            if has_orchestration and has_infrastructure:
                violations.append(str(relative))
        self.assertEqual(violations, [])

    def test_composition_uses_ports_and_policies_without_importing_api_or_infrastructure(self) -> None:
        violations = [
            str(path.relative_to(PROJECT_ROOT))
            for path in python_files("langHar/composition")
            if any(module.startswith(("langHar.api", "langHar.infrastructure", "langHar.bootstrap"))
                   for module in imported_modules(path))
        ]
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
