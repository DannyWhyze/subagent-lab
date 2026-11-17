"""Supervisor agent factory for smolagents pattern."""

from smolagents import CodeAgent, OpenAIServerModel


def create_supervisor(model: OpenAIServerModel, managed_agents: list[CodeAgent]) -> CodeAgent:
    """Instantiate supervisor CodeAgent orchestrating managed child subagents."""
    return CodeAgent(
        tools=[],
        model=model,
        name="supervisor",
        managed_agents=managed_agents,
        verbosity_level=0,
    )
