# DeepAgent with LangGraph checkpointer memory

This prototype extends `deep_agent_from_scratch` with LangGraph's `InMemorySaver` checkpointer to retain conversation history and virtual filesystem state across multiple turns.

---

## Architecture overview

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Supervisor as Supervisor Agent (LangGraph)
    participant Checkpointer as InMemorySaver (thread_id)
    participant TaskTool as task() Tool
    participant Subagent as Research Subagent
    participant VirtualFS as State Virtual Filesystem

    Note over User,Checkpointer: Turn 1 (Initial Research)
    User->>Supervisor: "Research MCP and save to mcp_overview.md" (thread_id="t1")
    Supervisor->>TaskTool: invoke task(description="...", subagent_type="research-agent")
    TaskTool->>Subagent: invoke({"messages": [subtask]})
    Subagent->>VirtualFS: write_file("mcp_overview.md", content)
    Subagent-->>TaskTool: "Saved file mcp_overview.md"
    TaskTool-->>Supervisor: Command(update={"files": {...}, "messages": [...]})
    Supervisor->>User: "I have researched MCP and saved it to mcp_overview.md."
    Supervisor->>Checkpointer: Save checkpoint (messages, files) under thread_id="t1"

    Note over User,Checkpointer: Turn 2 (Contextual Follow-Up Query)
    User->>Supervisor: "What protocol did we just discuss? Check files with ls." (thread_id="t1")
    Checkpointer-->>Supervisor: Restore prior messages and virtual files
    Note over Supervisor: Knows history: We discussed MCP!
    Supervisor->>VirtualFS: invoke ls()
    VirtualFS-->>Supervisor: ["mcp_overview.md"]
    Supervisor->>User: "We just discussed Model Context Protocol (MCP). The file 'mcp_overview.md' is preserved in the filesystem."
    Supervisor->>Checkpointer: Update checkpoint under thread_id="t1"
```

---

## Key differences from deep_agent_from_scratch

| Feature | `deep_agent_from_scratch` | `deep_agent_from_scratch_memory` |
| :--- | :--- | :--- |
| **Checkpointer** | None (`create_agent` called without checkpointer) | `checkpointer=InMemorySaver()` configured |
| **Invocation config** | Bare invocation without thread configuration | Invocation with `config={"configurable": {"thread_id": ...}}` |
| **Conversational scope** | Single turn | Multi-turn memory with pronoun and reference resolution |
| **File persistence** | Lost on process exit | Preserved across turns in the same thread session |
| **System prompt** | Basic supervisor instructions | Preamble suppression and silent tool calling rules |

---

## Running the test

```bash
uv run python legacy_scripts/deep_agent_from_scratch_memory/app_test.py
```
