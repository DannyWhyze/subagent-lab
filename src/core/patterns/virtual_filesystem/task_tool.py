"""Task delegation meta-tool factory with virtual filesystem state synchronization."""

from typing import Annotated, Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.core.patterns.virtual_filesystem.state import DeepAgentState

TASK_DESCRIPTION_PREFIX = """Delegate a research task to a specialized sub-agent with isolated context. Available agents:
{other_agents}
"""


def create_research_task_tool(subagents_by_name: dict[str, Any]) -> BaseTool:
    """Create task meta-tool synchronizing virtual files between subagents and supervisor."""
    agent_descriptions = [f"- {name}: Specialist agent" for name in subagents_by_name]
    description = TASK_DESCRIPTION_PREFIX.format(other_agents="\n".join(agent_descriptions))

    @tool(description=description)
    def task(
        description: str,
        subagent_type: str,
        state: Annotated[DeepAgentState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        """Delegate a research task to a specialized sub-agent with isolated context."""
        if subagent_type not in subagents_by_name:
            allowed = ", ".join([f"`{k}`" for k in subagents_by_name])
            return f"Error: invoked agent of type {subagent_type}, allowed: {allowed}"

        sub_agent = subagents_by_name[subagent_type]
        subagent_state = {**state, "messages": [{"role": "user", "content": description}]}
        result = sub_agent.invoke(subagent_state)

        # Standard LangChain v3 / deepagents pattern: extract clean text from last AIMessage
        content = ""
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage):
                text = msg.text.rstrip() if msg.text else ""
                if text:
                    content = text
                    break
        if not content and result.get("messages"):
            last_msg = result["messages"][-1]
            content = str(getattr(last_msg, "content", ""))

        return Command(
            update={
                "files": result.get("files", {}),
                "messages": [
                    ToolMessage(
                        content,
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    return task
