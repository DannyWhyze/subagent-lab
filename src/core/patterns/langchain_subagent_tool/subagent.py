"""Specialized child subagent definition for LangChain Subagent-as-Tool pattern."""

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel

from src.core.patterns.langchain_subagent_tool.tools import get_weather


def create_weather_specialist(model: BaseChatModel):
    """Instantiate child weather specialist subagent wrapped later in @tool."""
    return create_agent(
        name="weather_specialist",
        model=model,
        tools=[get_weather],
        system_prompt=(
            "You are a weather specialist. Always use get_weather to check real conditions. "
            "Execute tools sequentially and return a concise report."
        ),
    )
