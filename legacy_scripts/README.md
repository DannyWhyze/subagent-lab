# Subagent and multi-agent prototypes

Standalone prototype scripts comparing subagent delegation, state management, and orchestration patterns across LangGraph, DeepAgents, and Microsoft Agent Framework on local Ollama models (`qwen3.5:latest`).

---

## Architecture overview

```text
legacy_scripts/
├── subagents_personal_assistant_learn_lc/ # Pattern 1: Subagent-as-tool and human-in-the-loop
├── subagents_middleware/                 # Pattern 2: Declarative SubAgentMiddleware
├── deep_agent_subagent/                  # Pattern 3: create_deep_agent wrapper
├── dynamic_delegation_task_tool/         # Pattern 4: Dynamic delegation task tool
├── deep_agent_from_scratch/              # Pattern 5: DeepAgent with virtual filesystem
├── ms_agent_framework/                   # Pattern 6: Microsoft Agent Framework as_tool and debates
├── ast_code_agent/                       # Pattern 7: AST sandbox code agent
├── smolagents/                           # Pattern 8: Hugging Face smolagents (CodeAgent and ManagedAgent)
├── langgraph_round_robin_debate/         # Pattern 9: LangGraph round-robin debate
└── langgraph_moderated_debate/           # Pattern 10: LangGraph dynamic moderated debate
```

---

## 1. Pattern breakdown

### Pattern 1: Subagent-as-tool and human-in-the-loop
- **Location:** [`subagents_personal_assistant_learn_lc/`](./subagents_personal_assistant_learn_lc/)
- **Mechanism:** Wraps subagents inside standard `@tool` functions exposed directly to a parent supervisor.
- **Key concepts:**
  - **Human-in-the-loop interrupts:** Uses LangGraph checkpointer `interrupt()` signals before critical actions like calendar bookings or emails.
  - **Subagent execution:** Executes domain subagents (`calendar_agent`, `email_agent`) and coordinates dual-task delegation via `supervisor_agent` in [`app_test.py`](./subagents_personal_assistant_learn_lc/app_test.py).
  - **Sequential tool dispatch:** Prompts enforce single-tool execution to prevent local models from generating concatenated JSON strings.

---

### Pattern 2: Declarative `SubAgentMiddleware`
- **Location:** [`subagents_middleware/create_agent_middleware/`](./subagents_middleware/create_agent_middleware/)
- **Mechanism:** Combines LangChain `create_agent` with `deepagents.middleware.subagents.SubAgentMiddleware`.
- **Key concepts:**
  - **Mandatory backend:** `SubAgentMiddleware(backend=StateBackend(), subagents=[...])` requires a `BackendProtocol` instance. Omitting it raises a `TypeError`.
  - **Declarative specs:** Subagents are configured as typed dictionaries with their own prompts, models, and tool lists.

---

### Pattern 3: `create_deep_agent` wrapper
- **Location:** [`deep_agent_subagent/`](./deep_agent_subagent/)
- **Mechanism:** Batteries-included agent constructor from `deepagents`.
- **Key concepts:**
  - **Automatic backend fallback:** Instantiates `StateBackend()` automatically if omitted.
  - **Middleware stack:** Bundles `SubAgentMiddleware`, `FilesystemMiddleware` (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`), and `SummarizationMiddleware`.

---

### Pattern 4: Dynamic delegation (`task_tool`)
- **Location:** [`dynamic_delegation_task_tool/`](./dynamic_delegation_task_tool/)
- **Mechanism:** Direct LangGraph primitives (`@tool`, `InjectedState`, `Command`) without `deepagents` dependencies.
- **Key concepts:**
  - **Context isolation:** When calling `subagent.invoke(...)`, the meta-tool replaces parent messages with only the task prompt (`[{"role": "user", "content": task}]`).
  - **State injection:** Subagent findings return to the parent graph via `Command(update={"messages": [ToolMessage(...)]})`.

---

### Pattern 5: DeepAgent and virtual state filesystem
- **Location:** [`deep_agent_from_scratch/`](./deep_agent_from_scratch/)
- **Mechanism:** Combines dynamic task delegation with an in-memory virtual filesystem.
- **Key concepts:**
  - **In-memory filesystem:** File tools (`write_file`, `read_file`, `ls`) manipulate an ephemeral `state["files"]` dictionary via `Command` updates without touching the local disk.
  - **Cross-agent sharing:** A research subagent writes files into the shared state dictionary, and the supervisor reads artifacts from memory.

---

### Pattern 5b: DeepAgent with multi-turn memory
- **Location:** [`deep_agent_from_scratch_memory/`](./deep_agent_from_scratch_memory/)
- **Mechanism:** Extends Pattern 5 with LangGraph's `InMemorySaver` checkpointer under a persistent `thread_id`.
- **Key concepts:**
  - **Multi-turn dialogue:** Keeps conversation history across turns under the same `thread_id`, resolving follow-up questions without re-running subagent tasks.
  - **State file persistence:** Files in `state["files"]` persist across turns in the checkpointer state.

---

### Pattern 6: Microsoft Agent Framework (agent as tool)
- **Location:** [`ms_agent_framework/`](./ms_agent_framework/)
- **Mechanism:** Hierarchical caller-to-callee delegation using `agent.as_tool()` running locally through `OpenAIChatClient` directed at Ollama (`http://localhost:11434/v1`).
- **Scripts:**
  - [`agent_as_tool.py`](./ms_agent_framework/agent_as_tool.py): Supervisor delegates research tasks to an isolated `research_specialist` subagent.
  - [`weather_subagent_as_tool.py`](./ms_agent_framework/weather_subagent_as_tool.py): Two-level delegation. Supervisor calls `weather_specialist.as_tool()`, which calls `@tool get_weather`.
  - [`01_round_robin_group_chat.py`](./ms_agent_framework/01_round_robin_group_chat.py): Cyclic Writer-Reviewer workflow using `selection_func=round_robin_selection`.
  - [`round_robin_philosophical_debate.py`](./ms_agent_framework/round_robin_philosophical_debate.py): 8-persona debate where each persona speaks once in fixed order.
  - [`group_chat_philosophical_debate.py`](./ms_agent_framework/group_chat_philosophical_debate.py): Discussion panel with an LLM moderator choosing speakers.
- **Key concepts:**
  - **Caller-callee vs mesh:** `as_tool()` exposes the subagent as a standard function that returns to the caller, unlike peer-to-peer handoffs where control transfers permanently.
  - **Session isolation:** `propagate_session=False` (default) runs the subagent in a private sandbox without parent message history.
  - **API compatibility:** Using `agent-framework-openai` avoids version pinning conflicts with `langchain-ollama`.

---

### Pattern 7: Code-first agent and AST sandbox
- **Location:** [`ast_code_agent/`](./ast_code_agent/)
- **Mechanism:** Evaluates model-generated Python code in an in-memory `ASTSandbox` instead of JSON tool calls, without calling `eval()` or `exec()`.
- **Scripts:**
  - [`sandbox.py`](./ast_code_agent/sandbox.py): AST interpreter supporting binary operations, comparisons, loops, assignments, and whitelisted tools. It blocks imports and dunder attributes (`__`).
  - [`weather_tool.py`](./ast_code_agent/weather_tool.py): Deterministic weather mock tool.
  - [`app_test.py`](./ast_code_agent/app_test.py): Unit tests for security constraints and live test runner against Ollama.
- **Key concepts:**
  - **Code execution:** The agent filters data, runs loops, and calls multiple tools in a single Python script.
  - **Bounded execution:** Caps loop iterations (`max_loop_iterations=1000`) and limits built-ins (`print`, `len`, `range`, `str`, `sum`) to avoid CPU hangs.

---

### Pattern 8: Hugging Face smolagents (CodeAgent and ManagedAgent)
- **Location:** [`smolagents/`](./smolagents/)
- **Mechanism:** Uses `smolagents` with Ollama via `OpenAIServerModel(api_base="http://localhost:11434/v1")`.
- **Scripts:**
  - [`weather_tool.py`](./smolagents/weather_tool.py): Tool definition with the `@tool` decorator.
  - [`code_agent_test.py`](./smolagents/code_agent_test.py): CLI tests covering single `CodeAgent` execution and hierarchical `ManagedAgent` subagent delegation.
- **Key concepts:**
  - **Managed subagents:** A supervisor `CodeAgent` takes `managed_agents=[specialist_agent]`. In generated Python, the subagent is callable as a function (`specialist(task=...)`). The specialist runs its own ReAct loop and returns the result.
  - **Pluggable execution:** Uses `LocalPythonExecutor` by default, with optional switching to `DockerExecutor` or `E2BExecutor`.

---

### Pattern 9: LangGraph deterministic round-robin debate
- **Location:** [`langgraph_round_robin_debate/`](./langgraph_round_robin_debate/)
- **Mechanism:** Cyclic debate across 8 cultural personas using explicit LangGraph nodes, cycle edges, and v3 event streaming.
- **Scripts:**
  - [`round_robin_debate.py`](./langgraph_round_robin_debate/round_robin_debate.py): Standalone CLI script executing the 8-turn debate.
- **Key concepts:**
  - **Explicit graph topology:** Graph compiled as `START -> farmer -> developer -> teacher -> activist -> spiritual_leader -> artist -> immigrant -> doctor -> conditional edge [farmer, END]`.
  - **ChatML sanitization:** Wraps prior peer assistant messages as user turns (`[Author]: Content`) to prevent consecutive assistant turns from triggering immediate EOS on Qwen 3.5.
  - **Zero moderator overhead:** Runs without an LLM supervisor node.

---

### Pattern 10: LangGraph dynamic moderated debate
- **Location:** [`langgraph_moderated_debate/`](./langgraph_moderated_debate/)
- **Mechanism:** Hub-and-spoke supervisor graph where a central moderator selects speakers via Pydantic structured output (`ModeratorDecision`) and delivers a closing synthesis.
- **Scripts:**
  - [`moderated_debate.py`](./langgraph_moderated_debate/moderated_debate.py): Standalone CLI script with token streaming and transcript logging.
- **Key concepts:**
  - **Hub-and-spoke topology:** `START -> moderator -> conditional_edge -> [personas, END]`, with each persona returning to `moderator`.
  - **Pydantic structured routing:** Moderator calls `model.with_structured_output(ModeratorDecision)` with `config={"callbacks": []}` to keep internal routing JSON out of the public stream.
  - **Transition framing:** Moderator introduces each speaker with a tailored context question and closes with a 3-5 sentence synthesis.

---

## 2. Comparison matrix

| Metric | Pattern 1: Tool wrapper | Patterns 2 and 3: DeepAgents | Patterns 4 and 5: Dynamic delegation | Pattern 6: Microsoft as_tool | Patterns 7 and 8: Code-first |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Orchestration** | Tool calling (`@tool`) | Middleware interception | Dynamic `@tool task` | `agent.as_tool()` wrapper | Code execution (`CodeAgent`) |
| **Payload format** | Structured JSON | Structured JSON | Structured JSON | Structured JSON | Python script |
| **State management** | Single LangGraph state | In-memory `StateBackend` | LangGraph `StateGraph` | Encapsulated `Agent` runner | Sandbox memory |
| **Context isolation** | Low (shares prompt scope) | High (isolated child runs) | Strict (`[{"role": "user", "content": task}]`) | Complete (`propagate_session=False`) | Subagent sandbox |
| **Nested tool calls** | Manual inside function | Automatic via middleware | Subagent graph with tools | Native (subagent calls domain tools) | Python call (`specialist(task=...)`) |
| **Return handling** | String to tool node | Injected `ToolMessage` | LangGraph `Command` update | Function tool return value | `final_answer(...)` capture |
| **Local LLM stability** | Sensitive to parallel calls | Stable | Stable | Stable | High (Qwen writes valid Python) |

---

## 3. Local execution guidelines

1. **Windows console encoding:** Set `sys.stdout.reconfigure(encoding="utf-8")` at script startup to avoid Windows `cp1252` encoding crashes during model streaming.
2. **Deterministic fallbacks:** External tools (web search, weather) must provide local mock data so scripts run offline.
3. **Turn limits:** Enforce explicit turn limits and sequential tool dispatch in prompts when testing smaller local models.

---

## 4. Known limitations and gaps

1. **No peer-to-peer handoff scripts:** While theoretical differences between caller-callee (`as_tool`) and handoffs are documented, `legacy_scripts/` does not yet contain a runnable handoff script (such as Microsoft `HandoffBuilder` or LangGraph `Command(goto=...)`).
2. **Sequential execution only:** All scripts execute agent turns in serial order. Concurrent subagent dispatch (fan-out or map-reduce) is not implemented.
3. **In-process AST sandboxing:** `ASTSandbox` runs in-process without OS containerization (Docker or gVisor).
4. **Single-turn focus:** Only Pattern 5b (`deep_agent_from_scratch_memory`) uses checkpointer memory across multiple conversation turns. The other scripts run single tasks.
