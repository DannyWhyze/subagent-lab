"""Deterministic chess rules, move extraction, and board state formatting."""

import re

import chess


def extract_move(response: str) -> tuple[str | None, str | None]:
    """Extract <thought> and <move> from agent response with robust regex fallback."""
    thought_match = re.search(r"<thought>(.*?)</thought>", response, re.DOTALL | re.IGNORECASE)
    move_match = re.search(r"<move>(.*?)</move>", response, re.DOTALL | re.IGNORECASE)

    thought = thought_match.group(1).strip() if thought_match else None
    move_str = move_match.group(1).strip() if move_match else None

    if not move_str:
        words = re.findall(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b", response.lower())
        if words:
            move_str = words[0]

    return thought, move_str


def validate_human_move(board: chess.Board, move_str: str) -> tuple[chess.Move, str]:
    """Validate and push human move (UCI or SAN) on the board.

    Raises:
        ValueError: If move is illegal or cannot be parsed.
    """
    cleaned = move_str.strip()
    candidate: chess.Move | None = None

    # 1. Try UCI notation (e.g. e2e4)
    try:
        m = chess.Move.from_uci(cleaned.lower())
        if m in board.legal_moves:
            candidate = m
    except ValueError:
        pass

    # 2. Try SAN notation (e.g. e4, Nf3)
    if candidate is None:
        try:
            m = board.parse_san(cleaned)
            if m in board.legal_moves:
                candidate = m
        except ValueError:
            pass

    if candidate is None:
        legal_uci = [m.uci() for m in board.legal_moves]
        raise ValueError(f"Illegal move '{move_str}'. Legal moves: {', '.join(legal_uci[:10])}...")

    san_str = board.san(candidate)
    board.push(candidate)
    return candidate, san_str
