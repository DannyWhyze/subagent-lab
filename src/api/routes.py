"""FastAPI API routes for subagent pattern management and event streaming."""

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.sse_handler import sse_event_generator
from src.core.models import (
    ChessMoveRequest,
    ChessMoveResponse,
    ChessStateResponse,
    PatternMetadata,
    StreamRequest,
)
from src.core.patterns.ms_chess import MSChessRunner
from src.core.registry import registry

router = APIRouter(prefix="/api")


@router.get("/patterns", response_model=list[PatternMetadata])
async def list_patterns() -> list[PatternMetadata]:
    """Retrieve metadata for all registered subagent architectures."""
    return registry.get_metadata()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """System health check endpoint."""
    return {
        "status": "healthy",
        "patterns_count": len(registry.get_metadata()),
        "active_sessions": len(registry.session_store),
    }


@router.post("/stream")
async def stream_agent(request: Request, body: StreamRequest) -> StreamingResponse:
    """Execute an agent pattern and stream real-time events over SSE."""
    runner = registry.get_runner(body.pattern_id)
    if runner is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pattern '{body.pattern_id}' not found in registry.",
        )

    return StreamingResponse(
        sse_event_generator(runner=runner, request=request, req_data=body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chess/move", response_model=ChessMoveResponse)
async def move_chess(body: ChessMoveRequest) -> ChessMoveResponse:
    """Validate and apply a human chess move to a session game."""
    runner = registry.get_runner("ms_chess")
    if not isinstance(runner, MSChessRunner):
        raise HTTPException(
            status_code=500,
            detail="Conversational chess runner is not registered.",
        )

    try:
        candidate, san_str = runner.apply_human_move(body.session_id, body.move)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    board = runner.get_or_create_board(body.session_id)
    return ChessMoveResponse(
        valid=True,
        fen=board.fen(),
        san=san_str,
        last_move=candidate.uci(),
        game_over=board.is_game_over(),
        is_check=board.is_check(),
        legal_moves=[m.uci() for m in board.legal_moves],
    )


@router.get("/chess/state", response_model=ChessStateResponse)
async def get_chess_state(session_id: str) -> ChessStateResponse:
    """Retrieve the current board state and legal moves for a chess session."""
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")

    runner = registry.get_runner("ms_chess")
    if not isinstance(runner, MSChessRunner):
        raise HTTPException(
            status_code=500,
            detail="Conversational chess runner is not registered.",
        )

    board = runner.get_or_create_board(session_id)
    current_player = "White" if board.turn else "Black"
    return ChessStateResponse(
        session_id=session_id,
        fen=board.fen(),
        turn=board.fullmove_number,
        current_player=current_player,
        is_check=board.is_check(),
        is_game_over=board.is_game_over(),
        result=board.result() if board.is_game_over() else None,
        legal_moves=[m.uci() for m in board.legal_moves],
    )
