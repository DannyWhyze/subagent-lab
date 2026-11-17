from typing import NotRequired
from typing_extensions import TypedDict


class SubAgent(TypedDict):
    """Configuration specification for a specialized subagent."""

    name: str
    description: str
    prompt: str
    tools: NotRequired[list[str]]


weather_subagent_spec: SubAgent = {
    "name": "weather",
    "description": "This subagent can get weather in cities.",
    "prompt": "You are a weather specialist. Use the get_weather tool to retrieve the weather in a city.",
    "tools": ["get_weather"],
}
