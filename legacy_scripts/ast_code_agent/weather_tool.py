"""Standardized deterministic weather tool for AST code agent experimentation."""


def get_weather(city: str) -> str:
    """Return the current weather conditions for a specified city.

    Args:
        city: Name of the city to query.

    Returns:
        Formatted weather status string.
    """
    return f"The weather in {city} is sunny."
