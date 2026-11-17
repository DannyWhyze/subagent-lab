"""Hierarchical Subagent Pattern using Microsoft Agent Framework (Agent as a Tool).

This script demonstrates true caller-callee subagent delegation:
A supervisor coordinates requests and invokes an isolated specialist subagent
wrapped via `agent.as_tool()` like a standard function tool.
"""

import asyncio
import os
import sys

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

# Windows Console Encoding configuration (per AGENTS.md rules)
sys.stdout.reconfigure(encoding="utf-8")


def create_system(client: OpenAIChatClient) -> Agent:
    # 1. Specialized subagent (worker)
    # Operates in an isolated session and receives specific delegated tasks from the supervisor
    research_subagent = Agent(
        client=client,
        name="research_specialist",
        instructions=(
            "You are a technical research specialist. Analyze the given topic thoroughly "
            "and provide clear, structured findings. Do not engage in casual chat; "
            "return only the technical analysis."
        ),
    )

    # 2. Convert the subagent into a tool for the supervisor
    # propagate_session=False guarantees that the subagent runs inside an isolated session
    research_tool = research_subagent.as_tool(
        name="conduct_research",
        description="Delegate deep technical research questions to this specialist tool.",
        arg_name="task",
        arg_description="The specific research topic or question to investigate.",
        propagate_session=False,
    )

    # 3. Supervisor agent (coordinator)
    # Interacts with the user and decides when to invoke the subagent
    supervisor = Agent(
        client=client,
        name="supervisor",
        instructions=(
            "You are the main assistant coordinating user requests. "
            "When the user asks for in-depth technical analysis or comparisons, "
            "delegate the investigation to your conduct_research tool. "
            "Synthesize the tool's findings into a clear, cohesive final response for the user."
        ),
        tools=[research_tool],
    )

    return supervisor


async def main() -> None:
    # Local client via Ollama's OpenAI-compatible endpoint (100% local, no cloud dependencies)
    client = OpenAIChatClient(
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:latest"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",
    )

    supervisor = create_system(client)

    prompt = "Briefly compare LangGraph and Microsoft Agent Framework regarding subagents."
    print("=" * 80)
    print(f"User Prompt: {prompt}")
    print("=" * 80)

    # Execution: The supervisor orchestrates the entire delegation flow
    response = await supervisor.run(prompt)
    print("\nFinal Supervisor Response:")
    print("=" * 80)
    print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
