from __future__ import annotations

import ast
import unittest
from pathlib import Path


class LangHarIndependenceTests(unittest.TestCase):
    def test_langhar_does_not_import_thar(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        violations: list[str] = []

        for path in (project_root / "langHar").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(name.name == "thar" or name.name.startswith("thar.") for name in node.names):
                        violations.append(str(path.relative_to(project_root)))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module == "thar" or module.startswith("thar."):
                        violations.append(str(path.relative_to(project_root)))

        self.assertEqual(violations, [])
