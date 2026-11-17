"""Weather tool definition for Microsoft Agent Framework.

Aligned with the standard weather tool implementation across all subagent lab architectures.
"""

from agent_framework import tool


@tool(name="get_weather", description="Get the weather in a city.")
def get_weather(city: str) -> str:
    """Get the weather in a city."""
    return f"The weather in {city} is sunny"
