from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable

from langchain_core.tools import tool


_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 10:
            raise ValueError("指数绝对值不能超过 10。")
        result = _BINARY_OPERATORS[type(node.op)](_evaluate(node.left), right)
        if not math.isfinite(result) or abs(result) > 1e12:
            raise ValueError("计算结果必须是绝对值不超过 1e12 的有限实数。")
        return result
    raise ValueError("表达式只能包含数字、括号和基本算术运算符。")


@tool
def calculate(expression: str) -> str:
    """安全计算基本算术表达式。"""
    if len(expression) > 100:
        raise ValueError("表达式不能超过 100 个字符。")
    value = _evaluate(ast.parse(expression, mode="eval"))
    return str(int(value) if value.is_integer() else value)
