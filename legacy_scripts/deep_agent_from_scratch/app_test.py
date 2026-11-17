import sys

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from supervisor_agent import agent

query = (
    "Research what Model Context Protocol (MCP) is. "
    "Have the researcher save a short summary into 'mcp_overview.md'. "
    "Then list the files in the virtual filesystem."
)

stream = agent.stream_events(
    {"messages": [{"role": "user", "content": query}]},
    version="v3",
)

for kind, item in stream.interleave("messages", "tool_calls"):
    if kind == "messages":
        for token in item.text:
            print(token, end="", flush=True)
    elif kind == "tool_calls":
        print(f"\nTool call: {item.tool_name}({item.input})")
        for delta in item:
            pass
        print(f"Tool result: {item.output}")
