"""Supervisor agent factory for Microsoft Agent Framework as_tool pattern."""

from typing import Any

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient


def create_supervisor_agent(
    client: OpenAIChatClient,
    weather_subagent: Agent,
    default_options: dict[str, Any] | None = None,
) -> Agent:
    """Instantiate supervisor agent with weather specialist encapsulated via agent.as_tool()."""
    weather_tool = weather_subagent.as_tool(
        name="query_weather",
        description="Consult this specialist subagent to check weather conditions in any city.",
        arg_name="city",
        arg_description="The city to check the weather for.",
        propagate_session=False,
    )

    return Agent(
        client=client,
        name="supervisor",
        instructions=(
            "You are a coordinator assistant. When user asks for weather conditions in a city, "
            "you MUST call `query_weather(city=...)` immediately without preliminary remarks. "
            "Do not emit conversational preamble before calling tools. "
            "Synthesize the final answer for the user."
        ),
        tools=[weather_tool],
        default_options=default_options,
    )
