"""Dynamic task meta-tool factory for context-isolated delegation."""

from typing import Annotated, Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.core.patterns.dynamic_delegation.state import DynamicDelegationState

TASK_DESCRIPTION_PREFIX = """Delegate a task to a specialized sub-agent with isolated context. Available agents:
{other_agents}
"""


def create_task_tool(subagents_by_name: dict[str, Any]) -> BaseTool:
    """Create a @tool that delegates to child subagents with private state isolation."""
    agent_descriptions = [f"- {name}: Specialist agent" for name in subagents_by_name]
    description = TASK_DESCRIPTION_PREFIX.format(other_agents="\n".join(agent_descriptions))

    @tool(description=description)
    def task(
        description: str,
        subagent_type: str,
        state: Annotated[DynamicDelegationState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        """Delegate a task to a specialized sub-agent with isolated context."""
        if subagent_type not in subagents_by_name:
            allowed = ", ".join([f"`{k}`" for k in subagents_by_name])
            return f"Error: invoked agent of type {subagent_type}, allowed types are: {allowed}"

        sub_agent = subagents_by_name[subagent_type]
        # Context isolation: child receives only the targeted subtask
        subagent_state = {"messages": [{"role": "user", "content": description}]}
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
                "messages": [
                    ToolMessage(
                        content,
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    return task
