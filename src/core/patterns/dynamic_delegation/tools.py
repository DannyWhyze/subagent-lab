"""Deterministic domain tools for dynamic delegation pattern."""

from langchain_core.tools import tool


@tool
def get_weather(city: str) -> str:
    """Get the weather in a city."""
    return f"The weather in {city} is sunny, 22°C"
