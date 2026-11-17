"""Sample: Round-Robin Group Chat Orchestration (AutoGen Migration Pattern).

This script demonstrates deterministic cyclic multi-agent orchestration
using Microsoft Agent Framework's GroupChatBuilder with a Python selection function,
providing the direct equivalent to AutoGen's RoundRobinGroupChat.
Configured for local Ollama inference (qwen3.5:latest).
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import cast

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_framework import (
    Agent,
    AgentResponseUpdate,
    Message,
)
from agent_framework.orchestrations import GroupChatBuilder
from agent_framework_orchestrations._group_chat import GroupChatState
from dotenv import load_dotenv

from src.core.patterns.common.ms_client import OllamaCompatibleOpenAIChatClient

# Windows Console Encoding configuration (per AGENTS.md rules)
sys.stdout.reconfigure(encoding="utf-8")

# Load environment variables
load_dotenv()


def _get_chat_client() -> OllamaCompatibleOpenAIChatClient:
    """Return local Ollama chat client via OpenAI-compatible endpoint with ChatML role fix."""
    return OllamaCompatibleOpenAIChatClient(
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:latest"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",
    )


def round_robin_selection(state: GroupChatState) -> str:
    """Select the next speaker cyclically using pure Python modulo logic."""
    participant_names = list(state.participants.keys())
    return participant_names[state.current_round % len(participant_names)]


async def main() -> None:
    client = _get_chat_client()

    # 1. Define the writer agent
    writer = Agent(
        name="Writer",
        description="A technical writer who drafts clear and concise explanations",
        instructions="""
You are a technical writer. When given a task or critique, write or refine the explanation.
Keep your drafts concise, precise, and professional (under 4 sentences).
""",
        client=client,
    )

    # 2. Define the reviewer agent
    reviewer = Agent(
        name="Reviewer",
        description="A quality reviewer who critiques drafts and gives final approval",
        instructions="""
You are a rigorous code and content reviewer.
Review the draft provided by the Writer.
If the draft meets quality standards, end your response with the exact word: APPROVE.
If improvements are needed, give 1-2 specific suggestions for revision.
""",
        client=client,
    )

    # 3. Build the Round-Robin group chat
    # Stops when Reviewer approves or after a max of 6 rounds
    workflow = (
        GroupChatBuilder(
            participants=[writer, reviewer],
            selection_func=round_robin_selection,
            max_rounds=6,
            intermediate_output_from="all",
        )
        .with_termination_condition(
            lambda messages: any("APPROVE" in (msg.text or "") for msg in messages if msg.author_name == "Reviewer")
        )
        .build()
    )

    task = "Write a concise explanation of why subagent context isolation is important in AI workflows."
    print("=" * 80)
    print("ROUND-ROBIN GROUP CHAT: Writer-Reviewer Loop")
    print("=" * 80)
    print(f"Task: {task}")
    print("=" * 80 + "\n")

    last_response_id: str | None = None
    async for event in workflow.run(task, stream=True):
        if event.type in ("intermediate", "output"):
            data = event.data
            if isinstance(data, AgentResponseUpdate):
                if not data.text:
                    continue
                rid = data.response_id
                if rid != last_response_id:
                    if last_response_id is not None:
                        print("\n")
                    print(f"[{data.author_name}]:", end=" ", flush=True)
                    last_response_id = rid
                print(data.text, end="", flush=True)
            elif event.type == "output" and isinstance(data, list):
                outputs = cast(list[Message], data)
                print("\n" + "=" * 80)
                print("Final Conversation Transcript:")
                print("=" * 80)
                for message in outputs:
                    sender = message.author_name or message.role
                    print(f"\n[{sender}]:\n{message.text}")


if __name__ == "__main__":
    asyncio.run(main())
