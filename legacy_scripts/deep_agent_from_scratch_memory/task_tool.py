"""Task delegation meta-tool with context isolation."""

from collections.abc import Sequence
from typing import Annotated

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from research_subagent import SubAgent
from state import DeepAgentState

TASK_DESCRIPTION_PREFIX = """Delegate a research task to a specialized sub-agent with isolated context. Available agents:
{other_agents}
"""


def create_task_tool(
    tools: Sequence[BaseTool],
    subagents: list[SubAgent],
    model,
    state_schema: type = DeepAgentState,
):
    """Create a task delegation tool that enables context isolation through sub-agents.

    Args:
        tools: List of all available tools that can be assigned to sub-agents.
        subagents: List of sub-agent specifications.
        model: Language model instance.
        state_schema: State schema (defaults to DeepAgentState).

    Returns:
        The 'task' tool for dynamic sub-agent delegation.
    """
    agents = {}
    tools_by_name = {}

    for t in tools:
        if not isinstance(t, BaseTool):
            t = tool(t)
        tools_by_name[t.name] = t

    for _agent in subagents:
        if "tools" in _agent:
            assigned_tools = [tools_by_name[name] for name in _agent["tools"] if name in tools_by_name]
        else:
            assigned_tools = list(tools)

        agents[_agent["name"]] = create_agent(
            name=_agent["name"],
            model=model,
            system_prompt=_agent["prompt"],
            tools=assigned_tools,
            state_schema=state_schema,
        )

    other_agents_string = "\n".join([f"- {_agent['name']}: {_agent['description']}" for _agent in subagents])

    @tool(description=TASK_DESCRIPTION_PREFIX.format(other_agents=other_agents_string))
    def task(
        description: str,
        subagent_type: str,
        state: Annotated[DeepAgentState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        """Delegate a task to a specialized sub-agent with isolated context."""
        if subagent_type not in agents:
            allowed = ", ".join([f"`{k}`" for k in agents])
            return f"Error: invoked agent of type {subagent_type}, allowed: {allowed}"

        sub_agent = agents[subagent_type]

        # Context isolation: sub-agent sees only task description, shielding parent history
        subagent_state = {**state, "messages": [{"role": "user", "content": description}]}
        result = sub_agent.invoke(subagent_state)

        # Merge virtual files and return final sub-agent message
        return Command(
            update={
                "files": result.get("files", {}),
                "messages": [
                    ToolMessage(
                        result["messages"][-1].content,
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    return task
