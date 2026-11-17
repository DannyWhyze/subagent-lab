"""Specialized child subagent definition for smolagents pattern."""

from smolagents import CodeAgent, OpenAIServerModel

from src.core.patterns.smolagents.tools import get_weather


def create_weather_specialist(model: OpenAIServerModel) -> CodeAgent:
    """Instantiate specialized meteorological subagent with domain tools."""
    return CodeAgent(
        tools=[get_weather],
        model=model,
        name="weather_specialist",
        description="A specialized meteorological agent that looks up weather reports for given cities.",
        verbosity_level=0,
    )
