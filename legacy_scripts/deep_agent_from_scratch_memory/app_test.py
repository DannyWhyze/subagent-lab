"""Multi-Turn Memory Test for DeepAgent with InMemorySaver Checkpointer.

Demonstrates:
- Turn 1: Subagent research, virtual file creation ('mcp_overview.md'), and state checkpointing.
- Turn 2: Follow-up query under the same thread_id referring to prior dialogue and inspecting saved files.
"""

import sys

# Ensure UTF-8 output on Windows consoles (Rule in AGENTS.md)
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from supervisor_agent import agent

THREAD_ID = "deepagent-memory-test-session"
config = {"configurable": {"thread_id": THREAD_ID}}


def execute_turn(turn_number: int, query: str) -> None:
    print("\n" + "=" * 80)
    print(f"TURN {turn_number}: {query}")
    print("=" * 80)

    stream = agent.stream_events(
        {"messages": [{"role": "user", "content": query}]},
        config=config,
        version="v3",
    )

    print("\n[Stream Output]:")
    for kind, item in stream.interleave("messages", "tool_calls"):
        if kind == "messages":
            for token in item.text:
                print(token, end="", flush=True)
        elif kind == "tool_calls":
            print(f"\n-> Tool Call: {item.tool_name}({item.input})")
            for _ in item:
                pass
            print(f"<- Tool Result: {item.output}")
    print("\n")


if __name__ == "__main__":
    # Turn 1: Initial Research & Artifact Creation
    turn1_prompt = (
        "Research what Model Context Protocol (MCP) is. "
        "Have the researcher save a short summary into 'mcp_overview.md'."
    )
    execute_turn(1, turn1_prompt)

    # Turn 2: Conversational Follow-Up referencing previous turn & checking virtual files
    turn2_prompt = (
        "What protocol did we just discuss in our previous turn? "
        "Please check with `ls` what files are currently in the virtual filesystem."
    )
    execute_turn(2, turn2_prompt)
