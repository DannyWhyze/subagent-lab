"""In-memory virtual filesystem tools operating on DeepAgentState."""

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from state import DeepAgentState


@tool
def ls(state: Annotated[DeepAgentState, InjectedState]) -> list[str]:
    """List all files in the virtual filesystem stored in agent state."""
    return list(state.get("files", {}).keys())


@tool(parse_docstring=True)
def read_file(
    file_path: str,
    state: Annotated[DeepAgentState, InjectedState],
    offset: int = 0,
    limit: int = 2000,
) -> str:
    """Read file content from the virtual filesystem with line numbers.

    Args:
        file_path: Path to the file to read.
        state: Agent state containing the virtual filesystem.
        offset: Line number offset to start reading from (default: 0).
        limit: Maximum number of lines to read (default: 2000).

    Returns:
        Formatted file content with line numbers, or error if not found.
    """
    files = state.get("files", {})
    if file_path not in files:
        return f"Error: File '{file_path}' not found in virtual filesystem"

    content = files[file_path]
    if not content:
        return "System reminder: File exists but is empty."

    lines = content.splitlines()
    start_idx = offset
    end_idx = min(start_idx + limit, len(lines))

    if start_idx >= len(lines):
        return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"

    result_lines = []
    for i in range(start_idx, end_idx):
        result_lines.append(f"{i + 1:4d}\t{lines[i]}")

    return "\n".join(result_lines)


@tool(parse_docstring=True)
def write_file(
    file_path: str,
    content: str,
    state: Annotated[DeepAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Write content to a file in the virtual filesystem.

    Args:
        file_path: Name or path where the file should be saved.
        content: The text content to write into the file.
        state: Agent state containing the virtual filesystem.
        tool_call_id: Injected tool call identifier.

    Returns:
        Command updating agent state with the modified virtual file.
    """
    files = dict(state.get("files", {}))
    files[file_path] = content
    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(
                    f"Saved file '{file_path}' to virtual filesystem ({len(content)} characters).",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )
