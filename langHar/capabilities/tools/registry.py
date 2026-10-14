from langHar.capabilities.tools.builtin import (
    create_knowledge_list_tool,
    create_knowledge_search_tool,
)

TOOL_REGISTRY = {
    "knowledge_search": create_knowledge_search_tool,
    "knowledge_list_documents": create_knowledge_list_tool,
}
