"""Tools registered for execution inside the AST sandbox."""


def get_weather(city: str) -> str:
    """Return the current weather conditions for a specified city."""
    return f"The weather in {city} is sunny, 22°C"
