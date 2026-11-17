"""Data transfer objects and event payload schemas for Subagent Lab."""

import time
from typing import Any, Literal

from pydantic import BaseModel, Field


class StreamRequest(BaseModel):
    """Client request schema for starting an agent stream."""

    pattern_id: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_-]{1,64}$",
        description="Identifier of the subagent architectural pattern.",
    )
    session_id: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_-]{1,64}$",
        description="Client session identifier for state tracking.",
    )
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User prompt or task description (bounded to 4000 chars to prevent DoS).",
    )
    thinking: Literal["off", "low", "medium", "high"] = Field(
        default="off",
        description="Thinking/reasoning effort level: 'off' disables thinking, while 'low', 'medium', 'high' specify effort.",
    )


class StagePayload(BaseModel):
    """Payload representing a lifecycle execution stage change."""

    stage: str
    agent: str


class TokenPayload(BaseModel):
    """Payload representing a streamed text token."""

    delta: str
    source: str


class ThoughtPayload(BaseModel):
    """Payload representing streamed reasoning/thinking tokens."""

    delta: str
    source: str


class CodePayload(BaseModel):
    """Payload representing streamed executable code tokens."""

    delta: str
    source: str


class ToolCallPayload(BaseModel):
    """Payload representing a tool invocation or completion."""

    tool: str
    input: dict[str, Any]
    output: str | None = None


class SubagentPayload(BaseModel):
    """Payload representing dynamic delegation to a subagent."""

    name: str
    task: str


class MetricsPayload(BaseModel):
    """Payload containing runtime execution metrics."""

    ttft_ms: float
    total_duration_ms: float
    token_count: int
    tool_calls: int


class DonePayload(BaseModel):
    """Payload signaling completion with final answer."""

    final_answer: str


class ErrorPayload(BaseModel):
    """Payload signaling an execution or runtime error."""

    message: str
    code: str = "AGENT_ERROR"


class ChessBoardPayload(BaseModel):
    """Payload representing a validated chess game state snapshot."""

    fen: str
    turn: int
    current_player: str
    last_move: str | None = None
    san: str | None = None
    thought: str | None = None
    is_check: bool = False
    is_game_over: bool = False
    result: str | None = None
    legal_moves: list[str] = Field(default_factory=list)


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
    """Unified event object transmitted across SSE streams."""

    event_type: EventType
    payload: dict[str, Any]
    timestamp: float = Field(default_factory=time.time)


class PatternMetadata(BaseModel):
    """Descriptive metadata for registered agent paradigms."""

    id: str
    name: str
    description: str
    framework: str
    isolation_type: str
    example_prompts: list[str] = Field(
        default_factory=list,
        description="Curated example prompts tailored to the runner capabilities.",
    )


class ChessMoveRequest(BaseModel):
    """Client request schema for submitting a human chess move."""

    session_id: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_-]{1,64}$",
        description="Session identifier.",
    )
    move: str = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Move notation in UCI (e.g. e2e4) or SAN (e.g. e4, Nf3).",
    )


class ChessMoveResponse(BaseModel):
    """Response returned upon validating and applying a human chess move."""

    valid: bool
    fen: str
    san: str
    last_move: str
    game_over: bool
    is_check: bool
    legal_moves: list[str]


class ChessStateResponse(BaseModel):
    """Response representing the current chess game state for a session."""

    session_id: str
    fen: str
    turn: int
    current_player: str
    is_check: bool
    is_game_over: bool
    result: str | None = None
    legal_moves: list[str]
