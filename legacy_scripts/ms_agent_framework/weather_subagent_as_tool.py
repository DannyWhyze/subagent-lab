"""Nested Subagent Pattern with Custom Tool using Microsoft Agent Framework.

This script demonstrates two-level hierarchical execution:
1. Level 1 (Supervisor): Coordinates user requests and has `weather_subagent.as_tool()` as a tool.
2. Level 2 (Subagent): Specializes in weather, running its own loop, and has `@tool get_weather` as its tool.
"""

import asyncio
import os
import sys

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from weather_tool import get_weather

# Windows Console Encoding configuration (per AGENTS.md rules)
sys.stdout.reconfigure(encoding="utf-8")


def create_system(client: OpenAIChatClient) -> Agent:
    # 1. Specialized subagent (holds get_weather)
    weather_subagent = Agent(
        client=client,
        name="weather_specialist",
        instructions=(
            "You are a weather specialist. When asked about weather in a city, "
            "you MUST call get_weather to check the real conditions. "
            "Return a concise, factual weather report."
        ),
        tools=[get_weather],
    )

    # 2. Wrap subagent as an invocable FunctionTool
    weather_tool = weather_subagent.as_tool(
        name="query_weather",
        description="Consult this specialist tool to check weather conditions in any city.",
        arg_name="city",
        arg_description="The city to check the weather for.",
        propagate_session=False,
    )

    # 3. Supervisor (holds ONLY the subagent tool, not get_weather directly)
    supervisor = Agent(
        client=client,
        name="supervisor",
        instructions=(
            "You are a helpful assistant. You do not know weather data yourself. "
            "When the user asks about the weather in any location, call your query_weather tool. "
            "Answer the user's question politely using the information returned by query_weather."
        ),
        tools=[weather_tool],
    )

    return supervisor


async def main() -> None:
    # Local client via Ollama's OpenAI-compatible endpoint (100% local)
    client = OpenAIChatClient(
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:latest"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",
    )

    supervisor = create_system(client)

    prompt = "What is the current weather in Berlin?"
    print("=" * 80)
    print(f"User Request: {prompt}")
    print("=" * 80)

    # Execution of the hierarchical agent delegation
    response = await supervisor.run(prompt)
    print("\nFinal Supervisor Response:")
    print("=" * 80)
    print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
