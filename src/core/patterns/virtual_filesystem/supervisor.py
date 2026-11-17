"""Autonomous DeepAgent supervisor factory operating on a virtual filesystem."""

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.core.patterns.virtual_filesystem.state import DeepAgentState


def create_deep_agent_supervisor(
    model: BaseChatModel,
    tools: list[BaseTool],
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Instantiate supervisor agent with filesystem inspection tools and delegation."""
    return create_agent(
        name="supervisor",
        model=model,
        system_prompt=(
            "You are an autonomous DeepAgent supervisor coordinating complex workflows.\n"
            "Rules:\n"
            "1. Delegate research tasks to `research-agent` using the `task` tool immediately.\n"
            "2. Do not emit conversational preamble, status updates, or intermediate remarks before or between tool calls. Call tools first without speaking.\n"
            "3. You have a virtual filesystem in your state. Inspect and manage it using `ls`, `read_file`, and `write_file`.\n"
            "4. Always execute tools sequentially one at a time.\n"
            "5. Synthesize the final answer clearly for the user only after all tool operations are complete."
        ),
        tools=tools,
        state_schema=DeepAgentState,
        checkpointer=checkpointer,
    )
