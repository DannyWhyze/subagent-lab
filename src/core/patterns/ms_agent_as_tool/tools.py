"""Tools for Microsoft Agent Framework as_tool pattern."""

import agent_framework


@agent_framework.tool(name="get_weather", description="Get the weather in a city.")
def get_weather(city: str) -> str:
    """Get the weather in a city."""
    return f"The weather in {city} is sunny, 22°C"
