from langchain_core.tools import BaseTool

from langHar.capabilities.tools.builtin import calculate, get_weather, search


TOOL_REGISTRY: dict[str, BaseTool] = {
    search.name: search,
    get_weather.name: get_weather,
    calculate.name: calculate,
}
