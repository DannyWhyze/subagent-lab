from typing import Annotated, Sequence
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langchain.agents import create_agent
from langgraph.types import Command

from state import DeepAgentState
from weather_subagent import SubAgent

TASK_DESCRIPTION_PREFIX = """Delegate a task to a specialized sub-agent with isolated context. Available agents for delegation:
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
        tools: List of available tools that can be assigned to sub-agents.
        subagents: List of specialized sub-agent configurations.
        model: The language model to use for the sub-agents.
        state_schema: The state schema (defaults to DeepAgentState).

    Returns:
        A 'task' tool capable of delegating work to specialized sub-agents.
    """
    agents = {}

    tools_by_name = {}
    for t in tools:
        if not isinstance(t, BaseTool):
            t = tool(t)
        tools_by_name[t.name] = t

    for _agent in subagents:
        if "tools" in _agent:
            assigned_tools = [tools_by_name[name] for name in _agent["tools"]]
        else:
            assigned_tools = list(tools)

        agents[_agent["name"]] = create_agent(
            name=_agent["name"],
            model=model,
            system_prompt=_agent["prompt"],
            tools=assigned_tools,
            state_schema=state_schema,
        )

    other_agents_string = "\n".join(
        [f"- {_agent['name']}: {_agent['description']}" for _agent in subagents]
    )

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
            return f"Error: invoked agent of type {subagent_type}, the only allowed types are {allowed}"

        sub_agent = agents[subagent_type]

        # Context isolation: Create isolated state without parent conversation history
        subagent_state = {**state, "messages": [{"role": "user", "content": description}]}

        result = sub_agent.invoke(subagent_state)

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
