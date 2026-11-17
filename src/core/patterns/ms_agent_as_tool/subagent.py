"""Specialized child subagent definition for Microsoft Agent Framework."""

from typing import Any

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from src.core.patterns.ms_agent_as_tool.tools import get_weather


def create_weather_subagent(
    client: OpenAIChatClient,
    default_options: dict[str, Any] | None = None,
) -> Agent:
    """Instantiate specialized child weather subagent with domain tools."""
    return Agent(
        client=client,
        name="weather_specialist",
        instructions=(
            "You are a weather specialist. When asked about weather in a city, "
            "you MUST call get_weather to check real conditions. Return a concise report."
        ),
        tools=[get_weather],
        default_options=default_options,
    )
