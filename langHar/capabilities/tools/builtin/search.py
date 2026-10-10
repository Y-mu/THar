from langchain_core.tools import tool


@tool
def search(query: str) -> str:
    """搜索信息。"""
    return f"结果：{query}"
