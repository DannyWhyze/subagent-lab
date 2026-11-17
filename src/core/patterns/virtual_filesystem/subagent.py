"""Research subagent definition for virtual filesystem pattern."""

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.core.patterns.virtual_filesystem.state import DeepAgentState


def create_research_subagent(model: BaseChatModel, tools: list[BaseTool]):
    """Instantiate specialized research subagent writing to virtual filesystem."""
    return create_agent(
        name="research-agent",
        model=model,
        system_prompt=(
            "You are a technical research specialist.\n"
            "1. Search using web_search.\n"
            "2. Structure and write your findings to the virtual filesystem using write_file.\n"
            "3. Always execute tools sequentially one at a time."
        ),
        tools=tools,
        state_schema=DeepAgentState,
    )
