from supervisor_agent import agent

query = "What is the weather in Berlin?"

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
