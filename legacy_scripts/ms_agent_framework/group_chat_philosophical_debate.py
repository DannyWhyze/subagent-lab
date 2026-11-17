# Copyright (c) Microsoft. All rights reserved.

"""Sample: Philosophical Debate with Agent-Based Manager.

This script implements a multi-agent group chat workflow using Microsoft Agent Framework,
adapted to run completely locally via Ollama (using OpenAIChatClient).

Topic: "What does a good life mean to you personally?"

Participants represent:
- Farmer from Southeast Asia (tradition, sustainability, land connection)
- Software Developer from United States (innovation, technology, work-life balance)
- History Teacher from Eastern Europe (legacy, learning, cultural continuity)
- Activist from South America (social justice, environmental rights)
- Spiritual Leader from Middle East (morality, community service)
- Artist from Africa (creative expression, storytelling)
- Immigrant Entrepreneur from Asia in Canada (tradition + adaptation)
- Doctor from Scandinavia (public health, equity, societal support)
"""

import asyncio
import logging
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
from dotenv import load_dotenv

from src.core.patterns.common.ms_client import OllamaCompatibleOpenAIChatClient

# Windows Console Encoding configuration (per AGENTS.md rules)
sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.WARNING)

# Load environment variables from .env file
load_dotenv()


def _get_chat_client() -> OllamaCompatibleOpenAIChatClient:
    """Return local Ollama chat client via OpenAI-compatible endpoint with ChatML role fix."""
    return OllamaCompatibleOpenAIChatClient(
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:latest"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",
    )


async def main() -> None:
    # Create debate moderator with structured output for speaker selection
    # Note: Participant names and descriptions are automatically injected by the orchestrator
    moderator = Agent(
        name="Moderator",
        description="Guides philosophical discussion by selecting next speaker",
        instructions="""
You are a thoughtful moderator guiding a philosophical discussion on the topic handed to you by the user.

Your participants bring diverse global perspectives. Select speakers strategically to:
- NEVER select the same speaker twice in a row. Always select a DIFFERENT participant to respond.
- Create natural conversation flow and responses to previous points
- Ensure all voices are heard throughout the discussion
- Build on themes and contrasts that emerge
- Allow for respectful challenges and counterpoints
- Guide toward meaningful conclusions

Select speakers who can:
1. Respond directly to points just made
2. Introduce fresh perspectives when needed
3. Bridge or contrast different viewpoints
4. Deepen the philosophical exploration

Finish when:
- Multiple rounds have occurred (at least 6-8 exchanges)
- Key themes have been explored from different angles
- Natural conclusion or synthesis has emerged
- Diminishing returns in new insights

In your final_message, provide a brief synthesis highlighting key themes that emerged.
""",
        client=_get_chat_client(),
    )

    farmer = Agent(
        name="Farmer",
        description="A rural farmer from Southeast Asia",
        instructions="""
You're a farmer from Southeast Asia. Your life is deeply connected to land and family.
You value tradition and sustainability. You are in a philosophical debate.

Share your perspective authentically. Feel free to:
- Challenge other participants respectfully
- Build on points others have made
- Use concrete examples from your experience
- Keep responses thoughtful but concise (2-4 sentences)
""",
        client=_get_chat_client(),
    )

    developer = Agent(
        name="Developer",
        description="An urban software developer from the United States",
        instructions="""
You're a software developer from the United States. Your life is fast-paced and technology-driven.
You value innovation, freedom, and work-life balance. You are in a philosophical debate.

Share your perspective authentically. Feel free to:
- Challenge other participants respectfully
- Build on points others have made
- Use concrete examples from your experience
- Keep responses thoughtful but concise (2-4 sentences)
""",
        client=_get_chat_client(),
    )

    teacher = Agent(
        name="Teacher",
        description="A retired history teacher from Eastern Europe",
        instructions="""
You're a retired history teacher from Eastern Europe. You bring historical and philosophical
perspectives to discussions. You value legacy, learning, and cultural continuity.
You are in a philosophical debate.

Share your perspective authentically. Feel free to:
- Challenge other participants respectfully
- Build on points others have made
- Use concrete examples from history or your teaching experience
- Keep responses thoughtful but concise (2-4 sentences)
""",
        client=_get_chat_client(),
    )

    activist = Agent(
        name="Activist",
        description="A young activist from South America",
        instructions="""
You're a young activist from South America. You focus on social justice, environmental rights,
and generational change. You are in a philosophical debate.

Share your perspective authentically. Feel free to:
- Challenge other participants respectfully
- Build on points others have made
- Use concrete examples from your activism
- Keep responses thoughtful but concise (2-4 sentences)
""",
        client=_get_chat_client(),
    )

    spiritual_leader = Agent(
        name="SpiritualLeader",
        description="A spiritual leader from the Middle East",
        instructions="""
You're a spiritual leader from the Middle East. You provide insights grounded in religion,
morality, and community service. You are in a philosophical debate.

Share your perspective authentically. Feel free to:
- Challenge other participants respectfully
- Build on points others have made
- Use examples from spiritual teachings or community work
- Keep responses thoughtful but concise (2-4 sentences)
""",
        client=_get_chat_client(),
    )

    artist = Agent(
        name="Artist",
        description="An artist from Africa",
        instructions="""
You're an artist from Africa. You view life through creative expression, storytelling,
and collective memory. You are in a philosophical debate.

Share your perspective authentically. Feel free to:
- Challenge other participants respectfully
- Build on points others have made
- Use examples from your art or cultural traditions
- Keep responses thoughtful but concise (2-4 sentences)
""",
        client=_get_chat_client(),
    )

    immigrant = Agent(
        name="Immigrant",
        description="An immigrant entrepreneur from Asia living in Canada",
        instructions="""
You're an immigrant entrepreneur from Asia living in Canada. You balance tradition with adaptation.
You focus on family success, risk, and opportunity. You are in a philosophical debate.

Share your perspective authentically. Feel free to:
- Challenge other participants respectfully
- Build on points others have made
- Use examples from your immigrant and entrepreneurial journey
- Keep responses thoughtful but concise (2-4 sentences)
""",
        client=_get_chat_client(),
    )

    doctor = Agent(
        name="Doctor",
        description="A doctor from Scandinavia",
        instructions="""
You're a doctor from Scandinavia. Your perspective is shaped by public health, equity,
and structured societal support. You are in a philosophical debate.

Share your perspective authentically. Feel free to:
- Challenge other participants respectfully
- Build on points others have made
- Use examples from healthcare and societal systems
- Keep responses thoughtful but concise (2-4 sentences)
""",
        client=_get_chat_client(),
    )

    # Termination condition: stop after 10 assistant messages
    # Intermediate output from "all" streams participant updates as the conversation unfolds
    workflow = (
        GroupChatBuilder(
            participants=[farmer, developer, teacher, activist, spiritual_leader, artist, immigrant, doctor],
            intermediate_output_from="all",
            orchestrator_agent=moderator,
        )
        .with_termination_condition(lambda messages: sum(1 for msg in messages if msg.role == "assistant") >= 10)
        .build()
    )

    topic = "What does a good life mean to you personally?"

    print("\n" + "=" * 80)
    print("PHILOSOPHICAL DEBATE: Perspectives on a Good Life")
    print("=" * 80)
    print(f"\nTopic: {topic}")
    print("\nParticipants:")
    print("  - Farmer (Southeast Asia)")
    print("  - Developer (United States)")
    print("  - Teacher (Eastern Europe)")
    print("  - Activist (South America)")
    print("  - SpiritualLeader (Middle East)")
    print("  - Artist (Africa)")
    print("  - Immigrant (Asia -> Canada)")
    print("  - Doctor (Scandinavia)")
    print("\n" + "=" * 80)
    print("DISCUSSION BEGINS")
    print("=" * 80 + "\n")

    # Keep track of the current speaker to format output cleanly in streaming mode
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
            elif event.type == "output":
                # Final conversation transcript
                outputs = cast(list[Message], event.data)
                print("\n" + "=" * 80)
                print("\nFinal Conversation Transcript:\n")
                for message in outputs:
                    sender = message.author_name or message.role
                    print(f"{sender}: {message.text}\n")


if __name__ == "__main__":
    asyncio.run(main())
