# Frontend specification: Subagent Lab Explorer user interface

This document specifies the user interface for the `subagent_lab` web client, covering layout, component hierarchy, streaming lifecycle, DOM rendering rules, and client session persistence.

---

## 1. Architectural principles and stack

The frontend uses vanilla HTML5, CSS3, and JavaScript ES6 modules with no Node.js build step, bundler, or external runtime dependencies.
- **Developer labels (Rule 22)**: Buttons, badges, and status labels contain no decorative emojis. All controls use text labels, such as `[Run Query]`, `[Abort Run]`, `[Clear Output]`, and `[Status: Connected]`.
- **Session persistence (Rule 47)**: A page refresh restores active parameters, chat history, timeline stages, chessboard state, and benchmark metrics from `sessionStorage`.
- **DOM rendering without innerHTML reparsing**: Streaming tokens append via `document.createTextNode()` to the active message node, avoiding layout recalculation and text re-parsing during token generation.
- **Collapsible containers**: Thoughts, executed code, subagent delegations, and tool invocations render in collapsible `<details><summary>` boxes that start closed to keep the message timeline legible.

---

## 2. Directory and asset layout

```text
src/web/
├── index.html            # Single-page application HTML structure
├── css/
│   └── style.css         # Dark theme and layout styles
└── js/
    ├── app.js            # Controller, DOM bindings, and sessionStorage persistence
    ├── stream.js         # SSE reader client with AbortController lifecycle
    └── chess_board.js    # 8x8 Chessboard component and click-to-move interaction
```

---

## 3. UI component hierarchy and layout

The interface uses a two-column desktop layout (`app-main`):

```text
+---------------------------------------------------------------------------------------------------------------+
| Header: [Subagent Lab Explorer]   [Status: Connected]    Architecture: [Dropdown v]   Thinking: [Dropdown v] |
+---------------------------------------------------+-----------------------------------------------------------+
| Left Panel (flex: 6)                              | Right Panel (flex: 4)                                     |
| - Header: Execution & Dialogue                    | - Header: Live Telemetry                                  |
|   Buttons: [Run Query] [Abort Run] [Clear Output] | - Benchmark Metrics Card:                                 |
| - Chat & Stream Container (#chatContainer)        |   TTFT: 0.0 ms | Total: 0.0 ms                            |
|   - .user-message                                 |   Tokens: 0    | Tool Calls: 0                            |
|   - .thought-box (collapsible <details>)          | - Pattern Metadata Card:                                  |
|   - .code-box (collapsible <details>)             |   Framework | Isolation | Description                     |
|   - .subagent-box (collapsible <details>)         | - Execution Stage Timeline:                               |
|   - .tool-box (collapsible <details>)             |   [Stage: turn_Farmer]                                    |
|   - .assistant-message                            | - Chessboard Panel (#chess-panel):                        |
| - Example Prompt Chips (#examplesChips)           |   8x8 CSS Grid, SVG pieces, moves list                    |
| - Prompt Input Area (#promptInput)                |                                                           |
+---------------------------------------------------+-----------------------------------------------------------+
```

### 3.1 CSS design system (`src/web/css/style.css`)
- **Color values**:
  - Background dark: `#121418`
  - Panel background: `#1a1e24`
  - Card background: `#222730`
  - Border: `#333a46`
  - Primary blue: `#388bfd`
  - Success green: `#2ea043`
  - Abort red: `#da3633`
  - Subagent purple: `#a371f7`
  - Tool gold: `#d29922`
- **Typography**:
  - Sans-serif: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
  - Monospace: `ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace`
- **Collapsible boxes**:
  - `.thought-box`, `.code-box`, `.subagent-box`, and `.tool-box` use `display: block` and `flex-shrink: 0`.
  - Native `<summary>` bars use `min-height: 32px` and `padding: 8px 12px` to prevent Chromium flex-item height collapse when closed.

---

## 4. Client state and persistence schema (`sessionStorage`)

The client saves state to `sessionStorage` under the key `subagent_lab_session_state`.

### 4.1 Schema definition
```json
{
  "session_id": "sess_x8k2p9a1",
  "last_pattern_id": "dynamic_delegation",
  "last_thinking": "low",
  "chat_history": [
    {
      "type": "user",
      "content": "What is the weather in Berlin?"
    },
    {
      "type": "thought",
      "speaker": "supervisor",
      "content": "Checking user location request and preparing tool delegation."
    },
    {
      "type": "code",
      "speaker": "ast_code_agent",
      "content": "berlin_weather = get_weather('Berlin')\nfinal_answer({'Berlin': berlin_weather})"
    },
    {
      "type": "subagent",
      "name": "weather",
      "task": "Retrieve weather in Berlin"
    },
    {
      "type": "tool",
      "tool": "lc_get_weather",
      "output": "The weather in Berlin is sunny, 22°C"
    },
    {
      "type": "assistant",
      "content": "The weather in Berlin is currently sunny with a temperature of 22°C."
    }
  ],
  "stage_timeline": [
    {
      "stage": "turn_Farmer",
      "agent": "Farmer"
    }
  ],
  "metrics_summary": {
    "ttft": "142.5 ms",
    "duration": "1250.3 ms",
    "tokens": "84",
    "tool_calls": "1"
  },
  "chess_state": {
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "last_move": null,
    "player_color": "spectator"
  }
}
```

### 4.2 Lifecycle triggers
- **Save trigger (`saveSessionState()`)**: Runs on pattern selection, user query submission, incoming tool and subagent events, stream completion (`done`), stage updates, and metrics receipt.
- **Restore trigger (`restoreSessionState()`)**: Runs during `DOMContentLoaded`. Restores dropdown values, chat history nodes, timeline stages, chessboard state, and metric counters.
- **Purge trigger (`clearOutput()`)**: Runs when clicking `[Clear Output]`. Clears DOM nodes and removes `subagent_lab_session_state` from `sessionStorage`.

---

## 5. Streaming and abort client (`src/web/js/stream.js`)

### 5.1 Asynchronous fetch and SSE parsing
The stream reader consumes standard `fetch` response streams through `ReadableStreamDefaultReader`:
```javascript
export async function startStream(url, requestData, onEvent, onError, onComplete) {
    if (currentAbortController) {
        currentAbortController.abort();
    }
    currentAbortController = new AbortController();
    // Fetch with signal: currentAbortController.signal
    // Split incoming byte chunks on '\n\n'
    // Parse 'data: <JSON>' and pass to onEvent(parsed)
}
```

### 5.2 Abort handling (`abortStream()`)
When clicking `[Abort Run]`:
1. `abortStream()` calls `currentAbortController.abort()`.
2. The fetch stream rejects with `AbortError`.
3. The client dispatches a local stage event `[Stage: stream_aborted]`.
4. Buttons toggle to initial state (`[Run Query]` enabled, `[Abort Run]` disabled).
5. The backend detects the socket disconnect and cancels the inference task within 100 ms.

### 5.3 Thinking level normalization (`getEffectiveThinking()`)
Certain architectures (such as `ms_chess`) disable the thinking dropdown and set its value to `'disabled_na'`. The client calls `getEffectiveThinking()` in `app.js` before sending requests:
- Returns the current `thinkingSelect.value` when enabled (`"off"`, `"low"`, `"medium"`, `"high"`).
- Returns `"off"` when the dropdown is disabled, preventing HTTP 422 validation errors from FastAPI `StreamRequest`.

---

## 6. Conversational chessboard component (`src/web/js/chess_board.js`)

When selecting `ms_chess`, the `#chess-panel` card displays in the right inspection column.

### 6.1 DOM structure and CSS grid
- Container: `#chess-board-view.chess-board-view` configured as a CSS Grid with 8 columns and 8 rows (`repeat(8, 1fr)`).
- Square coloring: Alternating `.square-light` (`#2d3748`) and `.square-dark` (`#1a202c`).
- Coordinate markers: Minimal rank (1 to 8) and file (a to h) monospace indicators along the board perimeter.
- Highlights:
  - `.square-selected`: Blue border highlight (`#388bfd`) indicating piece selection.
  - `.square-target`: Centered green dot indicator representing legal destination squares for the selected piece.
  - `.square-last-move`: Gold background tint indicating the previous move source and destination.

### 6.2 Piece rendering (strict Rule 22 compliance)
To avoid Unicode emoji differences across operating systems and follow Rule 22:
- All six piece types (`K, Q, R, B, N, P`) render as inline SVG vector elements (`.chess-piece-svg`).
- Zero decorative Unicode emojis or external image files are used.
- White pieces use fill `#f0f4f8` with stroke `#2d3748`; Black pieces use fill `#1a1f26` with stroke `#cbd5e1`.

### 6.3 Game modes and interaction lifecycle
1. **Spectator mode (`[Spectator]`)**:
   - AI White versus AI Black match.
   - Real-time SSE updates through `chess_board` event streams update board squares, turn badges, and move notation without page reloads.
2. **Interactive human play (`[Play as White]`, `[Play as Black]`)**:
   - The user selects a friendly piece by clicking its square.
   - Legal destinations calculate from the validated move array emitted by `python-chess`.
   - Clicking a highlighted target square sends a move request (`POST /api/chess/move`).
   - On response (`200 OK`), the board updates and the client triggers an AI counter-turn stream (`prompt: "ai_counter_turn"`).
3. **Session persistence**:
   - The active FEN, last move, and player orientation save to `sessionStorage` under `chess_state`.
   - On page refresh, board state, move history, and orientation restore from `sessionStorage` (Rule 47).

---

## 7. Security, accessibility, and responsive layout

### 7.1 Client-side HTML and Markdown sanitization (`renderSafeMarkdown`)
To prevent cross-site scripting (XSS) from model outputs or tool payloads:
- Assistant markdown strings parsed by `window.marked.parse()` pass through a DOM sanitization function using browser-native `DOMParser`.
- **Blocked elements**: `<script>`, `<iframe>`, `<object>`, `<embed>`, `<style>`, and `<link>` nodes are removed.
- **Blocked attributes**: Inline event handler attributes starting with `on*` (`onload`, `onerror`, `onclick`) are stripped.
- **Blocked protocols**: URLs in `href` and `src` attributes prefixed with `javascript:` are rejected.

### 7.2 Non-intrusive error notifications (`showSystemNotice`)
- The UI avoids modal browser `alert()` dialogs.
- Missing prompts or configuration errors display in `#chatContainer` as styled `.message.system-message.error-message` nodes with red accent borders.

### 7.3 Accessibility and keyboard navigation
- Dynamic updates: `#statusBadge` and `#chatContainer` define `aria-live="polite"` for screen reader announcements.
- Keyboard accessible chessboard: Each square on the board has `role="button"`, `tabIndex = 0`, descriptive dynamic `aria-label` values (for example `e4, white Pawn` or `e5, empty`), and `Enter` / `Space` key event listeners mapping directly to `handleSquareClick`.
- Focus indicators: High-contrast blue outline `:focus-visible` styling indicates keyboard focus.

### 7.4 Responsive breakpoint (`@media (max-width: 960px)`)
- Viewport adaptation: On displays 960 px wide or smaller, the two-column desktop layout stacks vertically into a single-column scrollable page (`height: auto`, `min-height: 100vh`).
- Autoscroll threshold: `scrollToBottomIfNearEnd(el, threshold = 80)` only scrolls down if the scroll container is within 80 px of the bottom, avoiding disorienting jumps when inspecting earlier turns.
