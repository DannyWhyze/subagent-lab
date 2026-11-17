"""State schema for virtual filesystem DeepAgent pattern."""

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def file_reducer(left: dict[str, str] | None, right: dict[str, str] | None) -> dict[str, str]:
    """Merge two file dictionaries, with right side taking precedence."""
    if left is None:
        return right or {}
    if right is None:
        return left
    return {**left, **right}


class DeepAgentState(TypedDict):
    """DeepAgent state incorporating an in-memory virtual filesystem."""

    files: Annotated[dict[str, str], file_reducer]
    messages: Annotated[list[AnyMessage], add_messages]
