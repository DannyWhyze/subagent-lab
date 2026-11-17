"""Sample: Philosophical Debate using Deterministic Round-Robin Orchestration.

This script implements the 8-persona philosophical debate from Microsoft Agent Framework,
but replaces the dynamic LLM orchestrator with a deterministic Round-Robin selection function.
This guarantees that each global perspective speaks in sequence without duplicate turns,
token overhead, or empty-cache race conditions on local Ollama inference (qwen3.5:latest).
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
    """Deterministic cyclical selection guaranteeing that all voices speak in order."""
    participant_names = list(state.participants.keys())
    return participant_names[state.current_round % len(participant_names)]


def create_debate_participants(client: OllamaCompatibleOpenAIChatClient) -> list[Agent]:
    """Instantiate the 8 diverse global perspectives."""
    farmer = Agent(
        name="Farmer",
        description="A rural farmer from Southeast Asia valuing tradition and sustainability",
        instructions="""
You're a farmer from Southeast Asia. Your life is deeply connected to land and family.
You value tradition and sustainability. You are in a philosophical debate.
Share your perspective authentically. Respond thoughtfully and concisely (2-4 sentences).
""",
        client=client,
    )

    developer = Agent(
        name="Developer",
        description="An urban software developer from the United States",
        instructions="""
You're a software developer from the United States. Your life is fast-paced and technology-driven.
You value innovation, freedom, and work-life balance. You are in a philosophical debate.
Respond to the previous participants. Keep responses thoughtful and concise (2-4 sentences).
""",
        client=client,
    )

    teacher = Agent(
        name="Teacher",
        description="A retired history teacher from Eastern Europe",
        instructions="""
You're a retired history teacher from Eastern Europe. You bring historical and philosophical perspectives.
You value legacy, learning, and cultural continuity. Connect your thoughts to what others said.
Keep responses thoughtful and concise (2-4 sentences).
""",
        client=client,
    )

    activist = Agent(
        name="Activist",
        description="A young activist from South America focusing on social and environmental rights",
        instructions="""
You're a young activist from South America focusing on environmental and social justice.
Challenge or build upon the previous points. Keep responses thoughtful and concise (2-4 sentences).
""",
        client=client,
    )

    spiritual_leader = Agent(
        name="SpiritualLeader",
        description="A spiritual leader from the Middle East focusing on morality and community service",
        instructions="""
You're a spiritual leader from the Middle East. You provide insights grounded in morality and community service.
Relate your perspective to the earlier participants. Keep responses thoughtful and concise (2-4 sentences).
""",
        client=client,
    )

    artist = Agent(
        name="Artist",
        description="An artist from Africa celebrating storytelling and collective memory",
        instructions="""
You're an artist from Africa. You view life through creative expression and collective memory.
Weave the themes mentioned into your reflection. Keep responses thoughtful and concise (2-4 sentences).
""",
        client=client,
    )

    immigrant = Agent(
        name="Immigrant",
        description="An immigrant entrepreneur from Asia in Canada balancing tradition and adaptation",
        instructions="""
You're an immigrant entrepreneur in Canada. You balance cultural tradition with adaptation and enterprise.
Reflect on the discussion so far. Keep responses thoughtful and concise (2-4 sentences).
""",
        client=client,
    )

    doctor = Agent(
        name="Doctor",
        description="A doctor from Scandinavia focused on public health and societal equity",
        instructions="""
You're a doctor from Scandinavia. Your view is shaped by public health, equity, and structured societal support.
Provide a concluding perspective based on the panel discussion. Keep responses concise (2-4 sentences).
""",
        client=client,
    )

    return [farmer, developer, teacher, activist, spiritual_leader, artist, immigrant, doctor]


async def main() -> None:
    client = _get_chat_client()
    participants = create_debate_participants(client)

    # Round-Robin: Exactly 8 rounds (each of the 8 participants speaks once in order)
    workflow = (
        GroupChatBuilder(
            participants=participants,
            selection_func=round_robin_selection,
            max_rounds=len(participants),
            intermediate_output_from="all",
        )
        .build()
    )

    topic = "What does a good life mean to you personally?"

    print("\n" + "=" * 80)
    print("PHILOSOPHICAL DEBATE (ROUND-ROBIN): Perspectives on a Good Life")
    print("=" * 80)
    print(f"\nTopic: {topic}")
    print("\nParticipants (Speaking Order):")
    for idx, p in enumerate(participants, 1):
        print(f"  {idx}. {p.name} ({p.description})")
    print("\n" + "=" * 80)
    print("DISCUSSION BEGINS")
    print("=" * 80 + "\n")

    current_speaker: str | None = None
    async for event in workflow.run(f"Please begin the discussion on: {topic}", stream=True):
        if event.type in ("intermediate", "output"):
            data = event.data
            if isinstance(data, AgentResponseUpdate):
                author = data.author_name or "Unknown"
                if author != current_speaker:
                    if current_speaker is not None:
                        print("\n")
                    print(f"[{author}]:", end=" ", flush=True)
                    current_speaker = author

                # Stream delta tokens only, ignoring redundant full-text 'replace' chunks
                if data.contents:
                    for content in data.contents:
                        c_type = getattr(content, "type", None)
                        merge_mode = getattr(content, "merge_mode", "append")
                        if c_type == "text" and merge_mode != "replace":
                            print(getattr(content, "text", ""), end="", flush=True)
                elif data.text:
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
