"""Tools for LangChain Subagent-as-Tool pattern."""

from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool, tool


@tool
def get_weather(city: str) -> str:
    """Get the weather in a city."""
    return f"The weather in {city} is sunny, 22°C"


def create_subagent_tool(weather_subagent: Any) -> BaseTool:
    """Encapsulate the child subagent inside a standard callable function @tool."""

    @tool
    def query_weather(city: str) -> str:
        """Consult the specialized weather subagent to check weather conditions in any city."""
        result = weather_subagent.invoke(
            {"messages": [{"role": "user", "content": f"Check the current weather in {city}"}]}
        )
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage):
                text = msg.text.rstrip() if msg.text else ""
                if text:
                    return text
        if result.get("messages"):
            return str(getattr(result["messages"][-1], "content", ""))
        return ""

    return query_weather
