"""Unit tests for the Conversational Chess Runner."""

import pytest

from src.core.patterns.ms_chess import MSChessRunner


@pytest.mark.asyncio
async def test_ms_chess_runner_deterministic_init():
    runner = MSChessRunner(model_name="mock-model")
    events = []
    # Test 1-turn spectator stream
    async for ev in runner.run_stream("spectator:1", session_id="test_chess_1"):
        events.append(ev)

    event_types = [e.event_type for e in events]
    assert "stage" in event_types
    assert "chess_board" in event_types
    assert "done" in event_types

    # Verify chess_board payload structure
    board_events = [e for e in events if e.event_type == "chess_board"]
    assert len(board_events) >= 1
    assert "fen" in board_events[0].payload
    assert "turn" in board_events[0].payload
    assert "legal_moves" in board_events[0].payload


@pytest.mark.asyncio
async def test_ms_chess_runner_apply_human_move():
    runner = MSChessRunner(model_name="mock-model")
    session_id = "test_chess_human_1"

    # Valid move in UCI format
    move, _ = runner.apply_human_move(session_id, "e2e4")
    assert move.uci() == "e2e4"

    # Valid move in SAN format (Black's turn: e5)
    move_black, _ = runner.apply_human_move(session_id, "e5")
    assert move_black.uci() == "e7e5"

    # Illegal move should raise ValueError
    with pytest.raises(ValueError, match="Illegal move"):
        runner.apply_human_move(session_id, "e2e4")
