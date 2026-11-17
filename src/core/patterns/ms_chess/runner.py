"""Thin SSE streaming adapter for Microsoft Conversational Chess."""

import asyncio
import os
from collections.abc import AsyncGenerator

import chess

from src.core.base import BaseAgentRunner
from src.core.metrics import MetricsTracker
from src.core.models import (
    AgentStreamEvent,
    ChessBoardPayload,
    DonePayload,
    ErrorPayload,
    StagePayload,
    TokenPayload,
)
from src.core.patterns.common.ms_client import OllamaCompatibleOpenAIChatClient
from src.core.patterns.ms_chess.agents import create_black_agent, create_white_agent
from src.core.patterns.ms_chess.engine import validate_human_move
from src.core.patterns.ms_chess.orchestration import query_ai_move
from src.core.session_store import SessionStore


class MSChessRunner(BaseAgentRunner):
    """Conversational Chess Runner combining Microsoft Agent Framework and python-chess."""

    def __init__(
        self,
        session_store: SessionStore | None = None,
        model_name: str | None = None,
    ) -> None:
        self.session_store = session_store if session_store is not None else SessionStore()
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
        self.is_mock = self.model_name == "mock-model"
        self.white_agent = None
        self.black_agent = None

        if not self.is_mock:
            self.client = OllamaCompatibleOpenAIChatClient(
                model=self.model_name,
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                api_key="ollama",
            )
            self.white_agent = create_white_agent(self.client)
            self.black_agent = create_black_agent(self.client)

    def get_or_create_board(self, session_id: str) -> chess.Board:
        """Retrieve existing chess board or initialize a new standard board."""
        data = self.session_store.get(session_id)
        if data and "chess_board" in data and isinstance(data["chess_board"], chess.Board):
            return data["chess_board"]

        board = chess.Board()
        state = data or {}
        state["chess_board"] = board
        self.session_store.set(session_id, state)
        return board

    def reset_board(self, session_id: str) -> chess.Board:
        """Reset the game board to standard starting position."""
        board = chess.Board()
        data = self.session_store.get(session_id) or {}
        data["chess_board"] = board
        self.session_store.set(session_id, data)
        return board

    def apply_human_move(self, session_id: str, move_str: str) -> tuple[chess.Move, str]:
        """Validate and apply a human move (UCI or SAN) to the session board."""
        board = self.get_or_create_board(session_id)
        candidate, san_str = validate_human_move(board, move_str)

        data = self.session_store.get(session_id) or {}
        data["chess_board"] = board
        data["last_move_desc"] = f"Human played {san_str} ({candidate.uci()})"
        self.session_store.set(session_id, data)

        return candidate, san_str

    async def run_stream(
        self,
        prompt: str,
        session_id: str,
        thinking: str = "off",
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        metrics = MetricsTracker()
        metrics.start()

        board = self.get_or_create_board(session_id)
        last_move_desc: str | None = None
        data = self.session_store.get(session_id) or {}
        if "last_move_desc" in data:
            last_move_desc = data["last_move_desc"]

        turns_to_play = 2
        is_spectator = False
        lower_prompt = prompt.strip().lower()

        if lower_prompt.startswith("spectator"):
            is_spectator = True
            if ":" in lower_prompt:
                try:
                    turns_to_play = max(1, min(20, int(lower_prompt.split(":")[1])))
                except ValueError:
                    turns_to_play = 2
            else:
                turns_to_play = 4
        elif lower_prompt == "ai_counter_turn":
            turns_to_play = 1
        elif lower_prompt.startswith("reset"):
            board = self.reset_board(session_id)
            turns_to_play = 0

        yield AgentStreamEvent(
            event_type="stage",
            payload=StagePayload(
                stage="Chess Match Initialized",
                agent="ms_chess_orchestrator",
            ).model_dump(),
        )

        # Initial board state snapshot
        legal_uci = [m.uci() for m in board.legal_moves]
        initial_payload = ChessBoardPayload(
            fen=board.fen(),
            turn=board.fullmove_number,
            current_player="White" if board.turn == chess.WHITE else "Black",
            last_move=None,
            is_check=board.is_check(),
            is_game_over=board.is_game_over(),
            result=board.result() if board.is_game_over() else None,
            legal_moves=legal_uci,
        )
        yield AgentStreamEvent(
            event_type="chess_board",
            payload=initial_payload.model_dump(),
        )

        turn_count = 0
        try:
            while turn_count < turns_to_play and not board.is_game_over():
                turn_count += 1
                is_white = board.turn == chess.WHITE
                color_name = "White" if is_white else "Black"
                agent = self.white_agent if is_white else self.black_agent
                agent_name = "White_Attacker" if is_white else "Black_Strategist"

                yield AgentStreamEvent(
                    event_type="stage",
                    payload=StagePayload(
                        stage=f"Turn {board.fullmove_number}: {color_name} thinking",
                        agent=agent_name,
                    ).model_dump(),
                )

                if self.is_mock:
                    move = next(iter(board.legal_moves))
                    thought = "Mock tactical reasoning."
                else:
                    move, thought = await query_ai_move(
                        agent=agent,
                        board=board,
                        color_name=color_name,
                        last_move_desc=last_move_desc,
                    )

                san_move = board.san(move)
                board.push(move)
                last_move_desc = f"{color_name} ({agent_name}) played {san_move} ({move.uci()})"

                data["chess_board"] = board
                data["last_move_desc"] = last_move_desc
                self.session_store.set(session_id, data)

                metrics.record_token(10)
                yield AgentStreamEvent(
                    event_type="token",
                    payload=TokenPayload(
                        delta=f"[{agent_name}] {san_move}: {thought}\n",
                        source=agent_name,
                    ).model_dump(),
                )

                legal_uci = [m.uci() for m in board.legal_moves]
                turn_payload = ChessBoardPayload(
                    fen=board.fen(),
                    turn=board.fullmove_number,
                    current_player="White" if board.turn == chess.WHITE else "Black",
                    last_move=move.uci(),
                    san=san_move,
                    thought=thought,
                    is_check=board.is_check(),
                    is_game_over=board.is_game_over(),
                    result=board.result() if board.is_game_over() else None,
                    legal_moves=legal_uci,
                )
                yield AgentStreamEvent(
                    event_type="chess_board",
                    payload=turn_payload.model_dump(),
                )

                if is_spectator and turn_count < turns_to_play and not board.is_game_over():
                    await asyncio.sleep(0.5)

            final_msg = "Chess turn completed."
            if board.is_game_over():
                final_msg = f"Game Over! Result: {board.result()}"

            yield AgentStreamEvent(
                event_type="done",
                payload=DonePayload(final_answer=final_msg).model_dump(),
            )

        except Exception as exc:
            yield AgentStreamEvent(
                event_type="error",
                payload=ErrorPayload(
                    message=f"Chess execution error: {exc}",
                    code="CHESS_ERROR",
                ).model_dump(),
            )

        finally:
            yield AgentStreamEvent(
                event_type="metrics",
                payload=metrics.finish().model_dump(),
            )
