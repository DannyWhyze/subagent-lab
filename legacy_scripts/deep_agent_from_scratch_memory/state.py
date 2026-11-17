"""State schema for DeepAgent with virtual filesystem and checkpointer memory."""

from typing import Annotated, Literal, NotRequired

from langchain.agents import AgentState
from typing_extensions import TypedDict


class Todo(TypedDict):
    """Structured task item for tracking progress."""

    content: str
    status: Literal["pending", "in_progress", "completed"]


def file_reducer(left: dict[str, str] | None, right: dict[str, str] | None) -> dict[str, str]:
    """Merge two file dictionaries, with right side taking precedence."""
    if left is None:
        return right or {}
    if right is None:
        return left
    return {**left, **right}


class DeepAgentState(AgentState):
    """Extended agent state with virtual filesystem and task tracking."""

    todos: NotRequired[list[Todo]]
    files: Annotated[NotRequired[dict[str, str]], file_reducer]
