"""Standardized tools for smolagents using @tool decorator."""

from smolagents import tool


@tool
def get_weather(city: str) -> str:
    """Return the current weather conditions for a specified city.

    Args:
        city: The name of the city to query.

    Returns:
        Formatted weather status string.
    """
    return f"The weather in {city} is sunny, 22°C"
