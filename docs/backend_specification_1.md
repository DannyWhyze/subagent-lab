# Backend specification: unified architecture and streaming server

This document specifies the backend for `subagent_lab`: domain models, runner contracts, session storage, REST and SSE endpoints, and error handling.

---

## 1. Architectural overview and structure

The backend uses **FastAPI** (`fastapi>=0.115.0`) on **Uvicorn** (`uvicorn[standard]>=0.30.0`), organized into the following layers:
- **Core models (`src/core/models.py`)**: Pydantic v2 DTOs and event schemas.
- **Abstract contracts (`src/core/base.py`)**: `BaseAgentRunner` asynchronous generator interface.
- **Runtime metrics (`src/core/metrics.py`)**: TTFT, duration, token counts, and tool call tracking.
- **Session cache (`src/core/session_store.py`)**: In-memory `OrderedDict` with LRU eviction capped at 50 sessions.
- **Pattern runners (`src/core/patterns/`)**: Subagent implementations for LangGraph, Microsoft Agent Framework, and smolagents.
- **API routes (`src/api/`)**: REST routes, CORS settings, and SSE streaming with client disconnect cancellation.

---

## 2. Directory layout

```text
src/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── base.py                   # BaseAgentRunner abstract base class
│   ├── models.py                 # Pydantic models and DTOs
│   ├── metrics.py                # MetricsTracker (TTFT, duration, counts)
│   ├── session_store.py          # SessionStore with LRU eviction (MAX_SESSIONS = 50)
│   ├── registry.py               # RunnerRegistry and MockAgentRunner
│   └── patterns/
│       ├── __init__.py
│       ├── common/               # Shared utilities (OllamaCompatibleOpenAIChatClient)
│       │   ├── __init__.py
│       │   └── ms_client.py
│       ├── dynamic_delegation/   # LangGraph v3 dynamic task meta-tool pattern
│       │   ├── __init__.py
│       │   ├── state.py
│       │   ├── tools.py
│       │   ├── subagent.py
│       │   ├── task_tool.py
│       │   ├── supervisor.py
│       │   └── runner.py
│       ├── virtual_filesystem/   # DeepAgent virtual filesystem pattern
│       │   ├── __init__.py
│       │   ├── state.py
│       │   ├── file_tools.py
│       │   ├── research_tools.py
│       │   ├── subagent.py
│       │   ├── task_tool.py
│       │   ├── supervisor.py
│       │   └── runner.py
│       ├── langchain_subagent_tool/ # LangChain @tool subagent pattern
│       │   ├── __init__.py
│       │   ├── tools.py
│       │   ├── subagent.py
│       │   ├── supervisor.py
│       │   └── runner.py
│       ├── ast_code_agent/       # AST sandbox code agent pattern
│       │   ├── __init__.py
│       │   ├── sandbox.py
│       │   ├── tools.py
│       │   ├── agent.py
│       │   └── runner.py
│       ├── smolagents/           # Hugging Face smolagents managed agent pattern
│       │   ├── __init__.py
│       │   ├── tools.py
│       │   ├── subagent.py
│       │   ├── supervisor.py
│       │   └── runner.py
│       ├── ms_agent_as_tool/     # MS Agent Framework agent.as_tool() pattern
│       │   ├── __init__.py
│       │   ├── tools.py
│       │   ├── subagent.py
│       │   ├── supervisor.py
│       │   └── runner.py
│       ├── ms_round_robin/       # MS Agent Framework round-robin group chat
│       │   ├── __init__.py
│       │   ├── participants.py
│       │   ├── orchestration.py
│       │   └── runner.py
│       ├── ms_round_robin_debate/ # MS Agent Framework deterministic 8-persona debate
│       │   ├── __init__.py
│       │   ├── personas.py
│       │   ├── orchestration.py
│       │   └── runner.py
│       ├── ms_moderated_debate/  # MS Agent Framework dynamic LLM-moderated debate
│       │   ├── __init__.py
│       │   ├── personas.py
│       │   ├── orchestration.py
│       │   └── runner.py
│       ├── langgraph_round_robin_debate/ # LangGraph deterministic cyclic 8-persona debate
│       │   ├── __init__.py
│       │   ├── state.py
│       │   ├── personas.py
│       │   ├── orchestration.py
│       │   └── runner.py
│       ├── langgraph_moderated_debate/ # LangGraph dynamic hub-and-spoke moderated debate
│       │   ├── __init__.py
│       │   ├── state.py
│       │   ├── personas.py
│       │   ├── orchestration.py
│       │   └── runner.py
│       └── ms_chess/             # python-chess conversational chess match
│           ├── __init__.py
│           ├── engine.py
│           ├── agents.py
│           ├── orchestration.py
│           └── runner.py
├── main.py                       # FastAPI application entrypoint and lifespan
├── api/
│   ├── __init__.py
│   ├── routes.py                 # REST and SSE route definitions
│   └── sse_handler.py            # SSE generator with disconnect cancellation
└── web/                          # Static assets served via /static
```

---

## 3. Data contracts and payload schemas

### 3.1 Input DTO: `StreamRequest`
Path: `src/core/models.py`
```python
class StreamRequest(BaseModel):
    pattern_id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    session_id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    prompt: str = Field(..., min_length=1, max_length=4000)
    thinking: Literal["off", "low", "medium", "high"] = Field(
        default="off",
        description="Reasoning effort level: 'off' disables thinking, while 'low', 'medium', 'high' specify effort.",
    )
```
- **Validation rules**:
  - `pattern_id`: Alphanumeric, underscores, hyphens (1 to 64 characters).
  - `session_id`: Alphanumeric, underscores, hyphens (1 to 64 characters).
  - `prompt`: Between 1 and 4000 characters.
  - `thinking`: Must be `"off"`, `"low"`, `"medium"`, or `"high"`.

### 3.2 Event payloads
Path: `src/core/models.py`

| Payload class | Fields | Purpose |
| :--- | :--- | :--- |
| `StagePayload` | `stage: str`, `agent: str` | Lifecycle transition (e.g. `supervisor_start`, `turn_Writer`). |
| `ThoughtPayload` | `delta: str`, `source: str` | Reasoning chunk from the active agent. |
| `CodePayload` | `delta: str`, `source: str` | Executable code chunk during code-first execution. |
| `TokenPayload` | `delta: str`, `source: str` | Text chunk from the active agent. |
| `ToolCallPayload` | `tool: str`, `input: dict[str, Any]`, `output: Optional[str]` | Tool invocation record and execution output. |
| `SubagentPayload` | `name: str`, `task: str` | Delegation event to a specialized child agent. |
| `MetricsPayload` | `ttft_ms: float`, `total_duration_ms: float`, `token_count: int`, `tool_calls: int` | Benchmark statistics. |
| `DonePayload` | `final_answer: str` | Stream completion with aggregated response. |
| `ErrorPayload` | `message: str`, `code: str = "AGENT_ERROR"` | Error details. |
| `ChessBoardPayload` | `fen: str`, `turn: int`, `current_player: str`, `last_move: Optional[str]`, `san: Optional[str]`, `thought: Optional[str]`, `is_check: bool`, `is_game_over: bool`, `result: Optional[str]`, `legal_moves: list[str]` | Board snapshot with legal move options. |

### 3.3 Stream envelope: `AgentStreamEvent`
```python
EventType = Literal[
    "stage",
    "token",
    "thought",
    "code",
    "tool_call",
    "subagent",
    "metrics",
    "done",
    "error",
    "chess_board",
]

class AgentStreamEvent(BaseModel):
    event_type: EventType
    payload: Dict[str, Any]
    timestamp: float = Field(default_factory=time.time)
```

### 3.4 Chess move and state DTOs
Path: `src/core/models.py`

#### `ChessMoveRequest`
```python
class ChessMoveRequest(BaseModel):
    session_id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    move: str = Field(..., min_length=2, max_length=10)
```

#### `ChessMoveResponse`
```python
class ChessMoveResponse(BaseModel):
    valid: bool
    fen: str
    san: str
    last_move: str
    game_over: bool
    is_check: bool
    legal_moves: list[str]
```

#### `ChessStateResponse`
```python
class ChessStateResponse(BaseModel):
    session_id: str
    fen: str
    turn: int
    current_player: str
    is_check: bool
    is_game_over: bool
    result: str | None = None
    legal_moves: list[str]
```

---

## 4. Session storage (`SessionStore`)

Path: `src/core/session_store.py`
- **Class**: `SessionStore(max_sessions: int = 50)`
- **Data structure**: `collections.OrderedDict[str, dict[str, Any]]`
- **Eviction strategy**: Least Recently Used (LRU).
  - `get(session_id: str) -> Optional[dict]`: Moves key to end (`move_to_end`) and returns state.
  - `set(session_id: str, state: dict) -> None`: Inserts or updates state, calls `move_to_end()`. If `len > max_sessions`, calls `popitem(last=False)` to drop the oldest entry.
  - `delete(session_id: str) -> bool`: Deletes key if present.
  - `clear() -> None`: Clears all cached sessions.

---

## 5. Metrics tracking (`MetricsTracker`)

Path: `src/core/metrics.py`
- Measures timing with `time.perf_counter()`.
- **TTFT (Time to First Token)**: Measured when `record_token()` is first called: `(first_token_time - start_time) * 1000.0`.
- **Latency**: Total time measured when calling `finish()`.
- **Counters**: Tracks generated tokens and tool executions.

---

## 6. Runner registry and patterns

Path: `src/core/registry.py`

### 6.1 Pattern matrix
| Pattern ID | Framework | Name | Isolation architecture |
| :--- | :--- | :--- | :--- |
| `dynamic_delegation` | LangChain / LangGraph | Dynamic Delegation Task Tool | Caller-callee with isolated child state dict |
| `virtual_filesystem` | LangChain / LangGraph | DeepAgent Virtual Filesystem | Shared state dictionary (`files`) kept in memory per session |
| `langchain_subagent_tool` | LangChain / LangGraph | LangChain Subagent-as-Tool | ReAct child subagent wrapped inside standard function `@tool` |
| `ms_agent_as_tool` | Microsoft Agent Framework | Microsoft Agent as_tool | Two-level hierarchy via `agent.as_tool(propagate_session=False)` |
| `ms_round_robin` | Microsoft Agent Framework | Round-Robin GroupChat | Cyclic turn-taking (`state.current_round % len(participants)`) |
| `ms_round_robin_debate` | Microsoft Agent Framework | MS Round-Robin 8-Persona Debate | Cyclic rotation over 8 global cultural personas |
| `ms_moderated_debate` | Microsoft Agent Framework | MS Moderated 8-Persona Debate | LLM moderator selecting speakers and synthesizing final summary |
| `langgraph_round_robin_debate` | LangChain / LangGraph | LangGraph Round-Robin 8-Persona Debate | Cyclic peer mesh over 8 personas via LangGraph Graph API |
| `langgraph_moderated_debate` | LangChain / LangGraph | LangGraph Moderated 8-Persona Debate | Hub-and-spoke supervisor selecting speakers via Pydantic structured output |
| `ms_chess` | Microsoft Agent Framework | MS Conversational Chess | Multi-agent match with `python-chess` guardrails and real-time board stream |
| `ast_code_agent` | Custom AST Sandbox | AST Sandbox Code Agent | In-memory AST whitelist (blocks imports and dunder attributes) |
| `smolagents_managed` | Hugging Face smolagents | smolagents ManagedAgent | Code-as-action delegation to specialized managed agents |
| `mock_runner` | Builtin Test Mock | Deterministic Mock Runner | Fast offline verification yielding all event types without LLM inference |

### 6.2 LangGraph streaming
In `DynamicDelegationRunner`, `DeepAgentFilesystemRunner`, and `LangChainSubagentToolRunner`:
- Runs LangGraph streaming (`stream = agent.stream_events(..., version="v3")`) with `stream.interleave("messages", "tool_calls")`.
- In `DeepAgentFilesystemRunner`: Sets `self.checkpointer = InMemorySaver()` on the supervisor graph and passes `config = {"configurable": {"thread_id": session_id}}` on every call. This preserves conversation history and virtual files (`files`) across turns.
- When `kind == "messages"`: Text tokens come from `item.text`, and reasoning tokens come from `item.reasoning`.
- When `kind == "tool_calls"`: Input dictionaries are read from `getattr(item, "input", {})`. The generator drains the `ToolCallStream` channel before reading output:
```python
if hasattr(item, "__iter__"):
    for _ in item:
        pass
```

### 6.3 AST sandbox execution (`ASTCodeRunner`)
In `ASTCodeRunner` (`src/core/patterns/ast_code_agent/runner.py`):
1. **Code generation:** Streams Python code from Ollama, with optional `thought` events when reasoning mode is active.
2. **AST evaluation:** Uses `ASTSandbox` (`src/core/patterns/ast_code_agent/sandbox.py`) without `exec()` or `eval()`.
3. **Security rules:** Blocks imports (`ast.Import`, `ast.ImportFrom`), statement escapes (`ast.Try`, `ast.With`, `ast.Delete`), and dunder attributes (`__*`). Sets `max_loop_iterations=1000`.
4. **Tool calls:** Function calls in AST code (like `get_weather`) emit `tool_call` SSE events.

### 6.4 smolagents ManagedAgent execution (`SmolagentsRunner`)
In `SmolagentsRunner` (`src/core/patterns/smolagents/runner.py`):
1. **Setup:** `supervisor = CodeAgent(managed_agents=[weather_specialist])` using `OpenAIServerModel`.
2. **Reasoning translation:** Maps `thinking` to `extra_body={"reasoning_effort": "none" | "low" | "medium" | "high"}`.
3. **Background worker:** Runs `supervisor.run(prompt, stream=True)` in a background thread, feeding steps (`ChatMessageStreamDelta`, `ActionStep`, `FinalAnswerStep`) through an `asyncio.Queue` into the SSE stream.

---

## 7. API endpoints

### 7.1 Platform settings
Path: `src/main.py`
- On Windows (`sys.platform == "win32"`), sets `asyncio.WindowsProactorEventLoopPolicy()`.
- CORS allows `http://localhost:8000` and `http://127.0.0.1:8000`.

### 7.2 Endpoints
Path: `src/api/routes.py`

#### `GET /api/patterns`
- **Response**: `200 OK`
- **Content-Type**: `application/json`
- **Body**: Array of `PatternMetadata`:
  ```json
  [
    {
      "id": "dynamic_delegation",
      "name": "Dynamic Delegation Task Tool",
      "description": "LangGraph v3 supervisor with isolated child subagent state...",
      "framework": "LangChain / LangGraph",
      "isolation_type": "Caller-Callee (Private Subagent State)",
      "example_prompts": [
        "What is the weather in Berlin right now?",
        "Check the weather in Tokyo and tell me if it is sunny."
      ]
    }
  ]
  ```

#### `GET /api/health`
- **Response**: `200 OK`
- **Content-Type**: `application/json`
- **Body**:
  ```json
  {
    "status": "healthy",
    "patterns_count": 13,
    "active_sessions": 0
  }
  ```

#### `POST /api/stream`
- **Request Body**: `StreamRequest` JSON
- **Response**:
  - `200 OK` with `media_type="text/event-stream"`
  - `404 Not Found` if `pattern_id` is unknown
  - `422 Unprocessable Entity` if request validation fails
- **SSE format**:
  Emits each event as `data: <JSON_STRING>\n\n`.
  ```text
  data: {"event_type":"stage","payload":{"stage":"supervisor_start","agent":"supervisor"},"timestamp":1730480000.1}

  data: {"event_type":"token","payload":{"delta":"The ","source":"supervisor"},"timestamp":1730480000.2}

  data: {"event_type":"metrics","payload":{"ttft_ms":120.4,"total_duration_ms":850.2,"token_count":24,"tool_calls":1},"timestamp":1730480000.9}

  data: {"event_type":"done","payload":{"final_answer":"The weather in Berlin is sunny."},"timestamp":1730480001.0}
  ```

#### `POST /api/chess/move`
- **Request Body**: `ChessMoveRequest` JSON (`session_id: str`, `move: str` [UCI or SAN])
- **Response**:
  - `200 OK` with `ChessMoveResponse` (`valid: true`, `fen: str`, `san: str`, `last_move: str`, `game_over: bool`, `is_check: bool`, `legal_moves: list[str]`)
  - `400 Bad Request` if move is illegal
  - `422 Unprocessable Entity` if schema validation fails

#### `GET /api/chess/state`
- **Query Parameter**: `session_id: str` (validated against regex `^[a-zA-Z0-9_-]{1,64}$`)
- **Response**:
  - `200 OK` with `ChessStateResponse` (`fen`, `turn`, `current_player`, `is_check`, `is_game_over`, `result`, `legal_moves`). If no prior moves exist for the session, initializes and returns the starting board.
  - `400 Bad Request` if `session_id` format is invalid

### 7.3 Disconnect cancellation (`sse_handler.py`)
To avoid wasted GPU cycles on disconnected clients:
1. The agent runner executes inside an asynchronous task (`asyncio.create_task(run_task())`).
2. The SSE generator checks `await request.is_disconnected()` between events.
3. On disconnect, the server calls `task.cancel()` to stop model inference.

---

## 8. Reasoning mode control

All runners accept the reasoning parameter with matching signatures:
`run_stream(self, prompt: str, session_id: str, thinking: str = "off") -> AsyncGenerator[AgentStreamEvent, None]`

### 8.1 Framework adaptation
- **LangChain / LangGraph**:
  - `ChatOllama(model=..., reasoning=False)` when `thinking == "off"`.
  - `ChatOllama(model=..., reasoning=True)` when `thinking == "high"`, or string `"low"` / `"medium"`.
  - Reasoning chunks in `stream_events(..., version="v3")` are detected with `hasattr(item, "reasoning")` and yielded as `ThoughtPayload(delta=r_token, source=...)` events.
- **Microsoft Agent Framework**:
  - `Agent(client=..., default_options={"reasoning": {"effort": effort}})` where `effort` maps `"off"` to `"none"` and `"low"`/`"medium"`/`"high"` directly.
  - Streaming updates contain reasoning in `update.contents` with `getattr(content, "type", None) == "text_reasoning"`, yielded as `ThoughtPayload(delta=content.text, source=...)` events.
