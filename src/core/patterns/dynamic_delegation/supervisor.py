"""Supervisor agent graph factory for dynamic delegation."""

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.core.patterns.dynamic_delegation.state import DynamicDelegationState


def create_supervisor_agent(model: BaseChatModel, task_tool: BaseTool):
    """Instantiate supervisor agent configured with dynamic task delegation meta-tool."""
    return create_agent(
        name="supervisor",
        model=model,
        system_prompt=(
            "You are an expert supervisor coordinating specialized subagents.\n"
            "Rules:\n"
            "1. Delegate specific inquiries to the appropriate subagent via the `task` tool immediately.\n"
            "2. Do not emit conversational preamble or preliminary remarks before delegating. Call the tool first.\n"
            "3. Never call tools in parallel. Always invoke them sequentially.\n"
            "4. Synthesize the final answer clearly for the user once subagents complete their tasks."
        ),
        tools=[task_tool],
        state_schema=DynamicDelegationState,
    )
