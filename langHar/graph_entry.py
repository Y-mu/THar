"""LangGraph Server 入口：只有 langgraph.json 会加载这个模块。

图在这里从环境构造，因此它不会污染测试；真正的装配逻辑仍在 bootstrap。
"""

from __future__ import annotations

from langHar.bootstrap import create_agent_graph
from langHar.config import Settings


graph = create_agent_graph(Settings.from_env())

