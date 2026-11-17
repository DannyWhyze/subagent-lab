from typing import NotRequired
from typing_extensions import TypedDict


class SubAgent(TypedDict):
    """Configuration specification for a specialized sub-agent."""

    name: str
    description: str
    prompt: str
    tools: NotRequired[list[str]]


research_subagent_spec: SubAgent = {
    "name": "research-agent",
    "description": "Specialized agent for researching technical questions and saving summaries.",
    "prompt": (
        "You are an expert research subagent. Use web_search to find information. "
        "Always use write_file to save a comprehensive summary to the requested file in the virtual filesystem. "
        "Execute one tool call at a time sequentially."
    ),
    "tools": ["web_search", "write_file", "read_file", "ls", "think_tool"],
}
