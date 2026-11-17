"""Cultural personas, ChatML sanitizing, and node factory for LangGraph Round-Robin Debate."""

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from src.core.patterns.langgraph_round_robin_debate.state import RoundRobinDebateState

PERSONAS: list[dict[str, str]] = [
    {
        "name": "Farmer",
        "node": "farmer",
        "next": "developer",
        "description": "A rural farmer from Southeast Asia valuing tradition and sustainability",
        "instructions": (
            "You're a farmer from Southeast Asia. Your life is deeply connected to land and family. "
            "You value tradition and sustainability. You are in a philosophical debate. "
            "Share your perspective authentically. Respond thoughtfully and concisely (2-4 sentences)."
        ),
    },
    {
        "name": "Developer",
        "node": "developer",
        "next": "teacher",
        "description": "An urban software developer from the United States",
        "instructions": (
            "You're a software developer from the United States. Your life is fast-paced and technology-driven. "
            "You value innovation, freedom, and work-life balance. You are in a philosophical debate. "
            "Respond to the previous participants. Keep responses thoughtful and concise (2-4 sentences)."
        ),
    },
    {
        "name": "Teacher",
        "node": "teacher",
        "next": "activist",
        "description": "A retired history teacher from Eastern Europe",
        "instructions": (
            "You're a retired history teacher from Eastern Europe. You bring historical and philosophical perspectives. "
            "You value legacy, learning, and cultural continuity. Connect your thoughts to what others said. "
            "Keep responses thoughtful and concise (2-4 sentences)."
        ),
    },
    {
        "name": "Activist",
        "node": "activist",
        "next": "spiritual_leader",
        "description": "A young activist from South America focusing on social and environmental rights",
        "instructions": (
            "You're a young activist from South America focusing on environmental and social justice. "
            "Challenge or build upon the previous points. Keep responses thoughtful and concise (2-4 sentences)."
        ),
    },
    {
        "name": "SpiritualLeader",
        "node": "spiritual_leader",
        "next": "artist",
        "description": "A spiritual leader from the Middle East focusing on morality and community service",
        "instructions": (
            "You're a spiritual leader from the Middle East. You provide insights grounded in morality and community service. "
            "Relate your perspective to the earlier participants. Keep responses thoughtful and concise (2-4 sentences)."
        ),
    },
    {
        "name": "Artist",
        "node": "artist",
        "next": "immigrant",
        "description": "An artist from Africa celebrating storytelling and collective memory",
        "instructions": (
            "You're an artist from Africa. You view life through creative expression and collective memory. "
            "Weave the themes mentioned into your reflection. Keep responses thoughtful and concise (2-4 sentences)."
        ),
    },
    {
        "name": "Immigrant",
        "node": "immigrant",
        "next": "doctor",
        "description": "An immigrant entrepreneur from Asia in Canada balancing tradition and adaptation",
        "instructions": (
            "You're an immigrant entrepreneur in Canada. You balance cultural tradition with adaptation and enterprise. "
            "Reflect on the discussion so far. Keep responses thoughtful and concise (2-4 sentences)."
        ),
    },
    {
        "name": "Doctor",
        "node": "doctor",
        "next": "farmer",
        "description": "A doctor from Scandinavia focused on public health and societal equity",
        "instructions": (
            "You're a doctor from Scandinavia. Your view is shaped by public health, equity, and structured societal support. "
            "Provide a concluding perspective based on the panel discussion. Keep responses concise (2-4 sentences)."
        ),
    },
]

PERSONA_BY_NODE: dict[str, dict[str, str]] = {p["node"]: p for p in PERSONAS}


def _extract_text(content: Any) -> str:
    """Normalize structured content block lists or strings into plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _format_messages_for_ollama(messages: Sequence[BaseMessage], current_persona: str) -> list[BaseMessage]:
    """Reformat message history for ChatML templates on local Ollama models.

    Prevents consecutive assistant turns from triggering immediate EOS / empty responses.
    Prior assistant statements by other participants are wrapped as incoming dialog turns.
    """
    sanitized: list[BaseMessage] = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            author = getattr(msg, "name", None) or "Participant"
            if author != current_persona:
                text = _extract_text(msg.content)
                sanitized.append(HumanMessage(content=f"[{author}]: {text}"))
            else:
                sanitized.append(msg)
        else:
            sanitized.append(msg)
    return sanitized


def create_persona_node(persona_def: dict[str, str], model: ChatOllama):
    """Factory creating a standard LangGraph node function for a specific debate persona."""
    persona_name = persona_def["name"]
    instructions = persona_def["instructions"]

    def node_func(state: RoundRobinDebateState) -> dict[str, Any]:
        sanitized = _format_messages_for_ollama(state["messages"], persona_name)
        prompt = [SystemMessage(content=instructions), *sanitized]

        response = model.invoke(prompt)
        response.name = persona_name

        return {
            "messages": [response],
            "current_round": state.get("current_round", 0) + 1,
        }

    return node_func
