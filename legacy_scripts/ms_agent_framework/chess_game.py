"""Sample: Interactive Multi-Agent Chess Game (Microsoft Agent Framework).

Ported from Microsoft AutoGen's agentchat_chess_game sample to Microsoft Agent Framework
with local Ollama inference (e.g. qwen3.5:latest).

Demonstrates:
- Multi-agent interaction with strict tool-like guardrails
- Deterministic chess rule validation with python-chess
- AI vs. AI mode (Tactical White vs. Strategic Black)
- Human vs. AI mode (Human plays White or Black with UCI/SAN input)
"""

import argparse
import asyncio
import os
import random
import re
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import chess
from agent_framework import Agent
from dotenv import load_dotenv

from src.core.patterns.common.ms_client import OllamaCompatibleOpenAIChatClient

# Windows Console Encoding configuration (per AGENTS.md rules)
sys.stdout.reconfigure(encoding="utf-8")

# Windows Event Loop Policy (per AGENTS.md rules)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()


def extract_move(response: str) -> tuple[str | None, str | None]:
    """Extract <thought> and <move> from agent response with robust regex fallback."""
    thought_match = re.search(r"<thought>(.*?)</thought>", response, re.DOTALL | re.IGNORECASE)
    move_match = re.search(r"<move>(.*?)</move>", response, re.DOTALL | re.IGNORECASE)

    thought = thought_match.group(1).strip() if thought_match else None
    move_str = move_match.group(1).strip() if move_match else None

    # Fallback: if no <move> tags, search for valid UCI notation (e.g. e2e4, g1f3, e7e8q)
    if not move_str:
        words = re.findall(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b", response.lower())
        if words:
            move_str = words[0]

    return thought, move_str


def format_board(board: chess.Board) -> str:
    """Return clear Unicode representation of the chess board with borders."""
    return board.unicode(borders=True)


async def get_ai_move(
    agent: Agent,
    board: chess.Board,
    color_name: str,
    last_move_desc: str | None,
    max_retries: int = 3,
) -> tuple[chess.Move, str]:
    """Prompt the AI agent for a move and validate it against official chess rules."""
    legal_moves_list = [m.uci() for m in board.legal_moves]
    legal_moves_str = ", ".join(legal_moves_list)

    error_msg = ""
    for attempt in range(1, max_retries + 1):
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

        resp = await agent.run(prompt)
        text = resp.text or ""
        thought, move_str = extract_move(text)

        if not move_str:
            error_msg = "Could not find a valid move tag <move>...</move> in your answer."
            continue

        try:
            candidate = chess.Move.from_uci(move_str.lower())
            if candidate in board.legal_moves:
                final_thought = thought or "Tactical choice according to position."
                return candidate, final_thought
            else:
                error_msg = f"Move '{move_str}' is illegal in the current position."
        except ValueError:
            error_msg = f"'{move_str}' is not a valid UCI move string."

    # Guardrail fallback: If retries are exhausted, choose a random legal move to prevent halting
    fallback_move = random.choice(list(board.legal_moves))
    return fallback_move, "Fallback to legal safety move after retry limit."


def get_human_move(board: chess.Board, color_name: str) -> tuple[chess.Move, str]:
    """Prompt the human player for a move (supports both UCI e.g. e2e4 and SAN e.g. e4)."""
    legal_uci = [m.uci() for m in board.legal_moves]
    while True:
        try:
            user_input = input(f"\nYour turn ({color_name}) [e.g. {legal_uci[0]} or SAN]: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit"):
                print("Game aborted by user.")
                sys.exit(0)

            # 1. Try UCI format (e.g. e2e4)
            try:
                move = chess.Move.from_uci(user_input.lower())
                if move in board.legal_moves:
                    return move, "Human strategic decision."
            except ValueError:
                pass

            # 2. Try SAN format (e.g. e4, Nf3, O-O)
            try:
                move = board.parse_san(user_input)
                return move, "Human strategic decision."
            except ValueError:
                pass

            print(f"Illegal move '{user_input}'. Example legal moves: {', '.join(legal_uci[:8])}...")
        except (KeyboardInterrupt, EOFError):
            print("\nGame interrupted.")
            sys.exit(0)


async def play_chess(
    mode: str = "ai-vs-ai",
    human_color: str = "black",
    max_turns: int = 10,
    model_name: str | None = None,
) -> None:
    """Run the conversational chess game."""
    client = OllamaCompatibleOpenAIChatClient(
        model=model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:latest"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",
    )

    white_agent = Agent(
        name="White_Attacker",
        instructions=(
            "You are a competitive chess master playing White. "
            "You prefer aggressive, dynamic piece activity, pawn breaks, and initiative. "
            "Always pick one move from the provided legal moves list and justify it concisely."
        ),
        client=client,
    )

    black_agent = Agent(
        name="Black_Strategist",
        instructions=(
            "You are a master strategist playing Black. "
            "You value king safety, solid piece harmony, and counter-attacks. "
            "Always pick one move from the provided legal moves list and justify it concisely."
        ),
        client=client,
    )

    board = chess.Board()
    print("=" * 80)
    print("SUBAGENT LAB: Conversational Chess with Ollama & Microsoft Agent Framework")
    print(f"Mode: {mode.upper()} | Model: {client.model}")
    print("=" * 80)
    print("\nInitial Board:")
    print(format_board(board))
    print("\nGame begins!\n")

    turn_count = 0
    last_move_desc: str | None = None

    while not board.is_game_over():
        turn_count += 1
        if max_turns > 0 and turn_count > max_turns:
            print(f"\nReached max turns limit ({max_turns}). Concluding game demonstration.")
            break

        is_white_turn = board.turn == chess.WHITE
        current_color = "White" if is_white_turn else "Black"
        is_human = (mode == "human") and (
            (human_color.lower() == "white" and is_white_turn)
            or (human_color.lower() == "black" and not is_white_turn)
        )

        print("-" * 60)
        print(f"Turn {turn_count}: {current_color} to move")

        if is_human:
            move, thought = get_human_move(board, current_color)
            san_notation = board.san(move)
            print(f"[{current_color} (Human)]: {move.uci()} ({san_notation})")
        else:
            agent = white_agent if is_white_turn else black_agent
            move, thought = await get_ai_move(agent, board, current_color, last_move_desc)
            san_notation = board.san(move)
            print(f"[{agent.name} ({current_color})]: {move.uci()} ({san_notation})")
            print(f'  Thought: "{thought}"')

        board.push(move)
        last_move_desc = f"{current_color} played {move.uci()} ({san_notation})"

        print("\nCurrent Board:")
        print(format_board(board))

        if board.is_check():
            print("  [ALERT] CHECK!")

    print("\n" + "=" * 80)
    if board.is_checkmate():
        winner = "Black" if board.turn == chess.WHITE else "White"
        print(f"CHECKMATE! {winner} wins!")
    elif board.is_stalemate():
        print("STALEMATE! Game is a draw.")
    elif board.is_insufficient_material():
        print("DRAW! Insufficient material to checkmate.")
    elif board.can_claim_draw():
        print("DRAW claimable (threefold repetition or 50-move rule).")
    else:
        print(f"Game concluded at turn {turn_count}. Final FEN: {board.fen()}")
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversational Chess Game using Microsoft Agent Framework & Ollama")
    parser.add_argument("--human", action="store_true", help="Enable Human vs AI mode (default: AI vs AI).")
    parser.add_argument(
        "--human-color",
        choices=["white", "black"],
        default="black",
        help="Color for the human player (default: black).",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=6,
        help="Maximum turns to play in demonstration mode (default: 6, set 0 for unlimited).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Ollama model name (default: from .env or qwen3.5:latest).",
    )
    args = parser.parse_args()

    mode = "human" if args.human else "ai-vs-ai"
    asyncio.run(
        play_chess(
            mode=mode,
            human_color=args.human_color,
            max_turns=args.max_turns,
            model_name=args.model,
        )
    )


if __name__ == "__main__":
    main()
