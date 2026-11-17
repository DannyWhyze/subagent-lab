"""Turn orchestration and AI move selection with python-chess guardrails."""

import random

import chess
from agent_framework import Agent

from src.core.patterns.ms_chess.engine import extract_move


async def query_ai_move(
    agent: Agent,
    board: chess.Board,
    color_name: str,
    last_move_desc: str | None,
    max_retries: int = 3,
) -> tuple[chess.Move, str]:
    """Query LLM agent with python-chess legal moves and robust retry guardrail."""
    legal_moves_list = [m.uci() for m in board.legal_moves]
    if not legal_moves_list:
        raise ValueError("No legal moves available (game over).")

    legal_moves_str = ", ".join(legal_moves_list)
    error_msg = ""

    for _ in range(1, max_retries + 1):
        prompt = (
            f"CHESS GAME - TURN {board.fullmove_number}\n"
            f"You are playing as {color_name}.\n"
            f"Board FEN: {board.fen()}\n"
            f"Opponent's last move: {last_move_desc or 'None (Game start)'}\n"
            f"Your legal moves: {legal_moves_str}\n"
        )
        if error_msg:
            prompt += f"\nPREVIOUS ERROR: {error_msg}\nPlease select strictly from the legal moves list.\n"

        example_move = random.choice(legal_moves_list)
        prompt += (
            "\nProvide your brief tactical reasoning and chosen move in this exact format:\n"
            "<thought>Brief 1-sentence tactical evaluation</thought>\n"
            f"<move>{example_move}</move>\n"
        )

        try:
            resp = await agent.run(prompt)
            text = resp.text or ""
            thought, move_str = extract_move(text)
            if not move_str:
                error_msg = "Could not find a valid move tag <move>...</move> in your answer."
                continue

            candidate = chess.Move.from_uci(move_str.lower())
            if candidate in board.legal_moves:
                final_thought = thought or "Tactical choice according to position."
                return candidate, final_thought
            else:
                error_msg = f"Move '{move_str}' is illegal in current position."
        except Exception as exc:
            error_msg = f"Inference error: {exc}"

    fallback_move = random.choice(list(board.legal_moves))
    return fallback_move, "Fallback to legal safety move after retry limit."
