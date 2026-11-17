from typing import Annotated, NotRequired
from typing_extensions import TypedDict
from langchain.agents import AgentState


def file_reducer(left: dict[str, str] | None, right: dict[str, str] | None) -> dict[str, str]:
    """Merge two file dictionaries, with right side taking precedence."""
    if left is None:
        return right or {}
    elif right is None:
        return left
    return {**left, **right}


class DeepAgentState(AgentState):
    """Extended agent state that supports virtual file persistence and context isolation."""

    files: Annotated[NotRequired[dict[str, str]], file_reducer]
