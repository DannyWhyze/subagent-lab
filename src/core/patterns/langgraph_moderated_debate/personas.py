"""Cultural personas, moderator node, and ChatML sanitizing for LangGraph Moderated Debate."""

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END

from src.core.patterns.langgraph_moderated_debate.state import (
    ModeratedDebateState,
    ModeratorDecision,
)

PERSONAS: list[dict[str, str]] = [
    {
        "name": "Farmer",
        "node": "farmer",
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
        "description": "A young activist from South America focusing on social and environmental rights",
        "instructions": (
            "You're a young activist from South America focusing on environmental and social justice. "
            "Challenge or build upon the previous points. Keep responses thoughtful and concise (2-4 sentences)."
        ),
    },
    {
        "name": "SpiritualLeader",
        "node": "spiritual_leader",
        "description": "A spiritual leader from the Middle East focusing on morality and community service",
        "instructions": (
            "You're a spiritual leader from the Middle East. You provide insights grounded in morality and community service. "
            "Relate your perspective to the earlier participants. Keep responses thoughtful and concise (2-4 sentences)."
        ),
    },
    {
        "name": "Artist",
        "node": "artist",
        "description": "An artist from Africa celebrating storytelling and collective memory",
        "instructions": (
            "You're an artist from Africa. You view life through creative expression and collective memory. "
            "Weave the themes mentioned into your reflection. Keep responses thoughtful and concise (2-4 sentences)."
        ),
    },
    {
        "name": "Immigrant",
        "node": "immigrant",
        "description": "An immigrant entrepreneur from Asia in Canada balancing tradition and adaptation",
        "instructions": (
            "You're an immigrant entrepreneur in Canada. You balance cultural tradition with adaptation and enterprise. "
            "Reflect on the discussion so far. Keep responses thoughtful and concise (2-4 sentences)."
        ),
    },
    {
        "name": "Doctor",
        "node": "doctor",
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


def create_moderator_node(model: ChatOllama):
    """Factory creating the central supervisor node with structured routing and final synthesis."""
    structured_model = model.with_structured_output(ModeratorDecision)

    moderator_system_prompt = (
        "You are an impartial, insightful debate moderator presiding over a panel discussion.\n"
        "Available panel participants:\n"
        "- 'farmer': Southeast Asian farmer (tradition, soil, family harmony)\n"
        "- 'developer': US software developer (technology, innovation, work-life balance)\n"
        "- 'teacher': Eastern European history teacher (legacy, historical continuity)\n"
        "- 'activist': South American activist (social/environmental justice, systemic change)\n"
        "- 'spiritual_leader': Middle Eastern spiritual leader (morality, communal covenant)\n"
        "- 'artist': African artist (creative expression, collective memory)\n"
        "- 'immigrant': Asian-Canadian entrepreneur (adaptation, building bridges)\n"
        "- 'doctor': Scandinavian doctor (public health equity, structured societal support)\n\n"
        "Evaluate the discussion flow and choose the participant whose perspective would most constructively "
        "enrich or challenge the conversation. Do not select the same person twice in a row. "
        "If all necessary perspectives have been heard or the debate is exhaustive, select 'FINISH'."
    )

    synthesis_system_prompt = (
        "You are the debate moderator. The discussion is concluded. "
        "Synthesize the key philosophical tensions, common ground, and core insights from all speakers. "
        "Deliver a cohesive, inspiring final summary (3-5 sentences) and formally close the debate."
    )

    def moderator_node(state: ModeratedDebateState) -> dict[str, Any]:
        current_r = state.get("current_round", 0)
        max_r = state.get("max_rounds", 6)

        # 1. Termination condition reached: perform final synthesis
        if current_r >= max_r:
            sanitized = _format_messages_for_ollama(state["messages"], "Moderator")
            prompt = [SystemMessage(content=synthesis_system_prompt), *sanitized]
            synthesis_msg = model.invoke(prompt)
            synthesis_msg.name = "Moderator"
            return {
                "messages": [synthesis_msg],
                "next_speaker": END,
            }

        # 2. Dynamic routing decision via structured output (callbacks suppressed to avoid leaking internal JSON into stream)
        sanitized = _format_messages_for_ollama(state["messages"], "Moderator")
        prompt = [SystemMessage(content=moderator_system_prompt), *sanitized]

        decision: ModeratorDecision = structured_model.invoke(prompt, config={"callbacks": []})

        # 3. If moderator decided to finish early: synthesize and terminate
        if decision.next_speaker == "FINISH":
            prompt = [SystemMessage(content=synthesis_system_prompt), *sanitized]
            synthesis_msg = model.invoke(prompt)
            synthesis_msg.name = "Moderator"
            return {
                "messages": [synthesis_msg],
                "next_speaker": END,
            }

        # 4. Otherwise, route to selected persona with optional transition framing
        speaker_title = decision.next_speaker.replace("_", " ").title()
        if decision.question_or_context and decision.question_or_context.strip():
            transition_text = (
                f"Thank you. Next, let us hear from our {speaker_title}: "
                f"{decision.question_or_context.strip()}"
            )
        else:
            transition_text = (
                f"Thank you. Let us now hear from our {speaker_title} "
                "to share their perspective on this discussion."
            )
        transition_msg = AIMessage(content=transition_text, name="Moderator")

        return {
            "messages": [transition_msg],
            "next_speaker": decision.next_speaker,
            "current_round": current_r + 1,
        }

    return moderator_node


def create_persona_node(persona_def: dict[str, str], model: ChatOllama):
    """Factory creating a standard LangGraph node function for a specialist persona."""
    persona_name = persona_def["name"]
    instructions = persona_def["instructions"]

    def node_func(state: ModeratedDebateState) -> dict[str, Any]:
        sanitized = _format_messages_for_ollama(state["messages"], persona_name)
        prompt = [SystemMessage(content=instructions), *sanitized]

        response = model.invoke(prompt)
        response.name = persona_name

        return {
            "messages": [response],
        }

    return node_func
