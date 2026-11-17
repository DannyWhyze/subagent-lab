"""Sample: Philosophical Debate with Dynamic LLM Moderator in LangGraph.

This script implements a hierarchical supervisor (hub-and-spoke) debate architecture
using LangGraph Graph API standards (Nodes, Explicit Edges, Pydantic Structured Output,
and v3 Content-Block Event Streaming).

Reference Documentation:
- Graph API Nodes: https://docs.langchain.com/oss/python/langgraph/graph-api-nodes
- Multi-Agent Supervisor: Centralized router evaluating conversation state and delegating turns.
- v3 Streaming: stream_events(..., version="v3") via GraphRunStream / stream.messages
"""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel, Field

# Enforce Windows UTF-8 console output per AGENTS.md rules
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()


class ModeratedDebateState(MessagesState):
    """Debate state tracking conversation messages, active speaker, and round counter."""

    current_round: int = 0
    max_rounds: int = 6
    next_speaker: str = "moderator"


class ModeratorDecision(BaseModel):
    """Pydantic structured output schema for the debate moderator."""

    thought: str = Field(
        description="Analysis of the arguments so far and which cultural perspective is needed next."
    )
    next_speaker: Literal[
        "farmer",
        "developer",
        "teacher",
        "activist",
        "spiritual_leader",
        "artist",
        "immigrant",
        "doctor",
        "FINISH",
    ] = Field(
        description="The persona chosen to speak next based on conversation flow, or FINISH if debate is complete."
    )
    question_or_context: str = Field(
        description="Brief guidance or question framing the turn for the chosen participant."
    )


# Specifications of the 8 diverse global perspectives
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
    """Extract plain text from string or structured content block list."""
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
    """Standard LangGraph node function per Graph API specifications.

    Takes application state as input, invokes the underlying LLM with role instructions,
    and returns a state update dict with the appended message.
    """
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


def build_moderated_debate_graph(model: ChatOllama):
    """Compile the LangGraph hub-and-spoke supervisor graph with explicit nodes and edges.

    Graph Topology:
      START -> moderator
      moderator -> conditional edge (lambda s: s["next_speaker"]) -> [farmer, developer, ..., doctor, END]
      [farmer, developer, ..., doctor] -> moderator (returns control back to supervisor)
    """
    builder = StateGraph(ModeratedDebateState)

    # 1. Register the central supervisor (moderator) node
    builder.add_node("moderator", create_moderator_node(model))

    # 2. Register all 8 specialist persona nodes
    for persona_def in PERSONAS:
        node_name = persona_def["node"]
        builder.add_node(node_name, create_persona_node(persona_def, model))

    # 3. Explicit initial edge: Start directly at the moderator
    builder.add_edge(START, "moderator")

    # 4. Explicit conditional edge: Moderator routes dynamically to the selected participant or END
    possible_targets = [p["node"] for p in PERSONAS] + [END]
    builder.add_conditional_edges(
        "moderator",
        lambda state: state["next_speaker"],
        possible_targets,
    )

    # 5. Explicit hub-and-spoke return edges: Every participant returns control to the moderator
    for persona_def in PERSONAS:
        builder.add_edge(persona_def["node"], "moderator")

    return builder.compile()


def run_moderated_debate(max_turns: int = 6, topic: str | None = None, thinking: str = "off") -> None:
    """Execute the multi-agent moderated debate using native LangGraph v3 stream_events."""
    if topic is None:
        topic = "Can technological progress coexist with ecological sustainability and social justice?"

    model_name = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    reasoning_param: bool | str = False if thinking == "off" else (True if thinking == "high" else thinking)

    print("=" * 80)
    print("LangGraph Multi-Agent Moderated Debate (v3 Streaming Hub-and-Spoke)")
    print("=" * 80)
    print(f"Model: {model_name} @ {base_url}")
    print(f"Topic: '{topic}'")
    print(f"Configured Max Turns: {max_turns}")
    print(f"Thinking Mode: {thinking}")
    print("=" * 80)

    model = ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.7,
        reasoning=reasoning_param,
    )

    graph = build_moderated_debate_graph(model)

    initial_state = {
        "messages": [HumanMessage(content=f"Topic for panel debate: {topic}")],
        "current_round": 0,
        "max_rounds": max_turns,
        "next_speaker": "moderator",
    }

    # Opt-in to official LangGraph version="v3" event streaming
    stream = graph.stream_events(
        initial_state,
        version="v3",
        config={"recursion_limit": max(50, max_turns * 4)},
    )

    ai_responses: list[AIMessage] = []

    # Stream model messages via stream.messages typed projection
    for msg in stream.messages:
        node_id = getattr(msg, "node", "unknown")
        if node_id == "moderator":
            persona_name = "Moderator"
            persona_desc = "Central Supervisor presiding over debate flow"
        else:
            persona_info = PERSONA_BY_NODE.get(node_id, {})
            persona_name = persona_info.get("name", node_id.capitalize())
            persona_desc = persona_info.get("description", "")

        print(f"\n[{persona_name}] ({persona_desc}):")
        print("-" * 70)

        # Stream reasoning tokens if available
        if getattr(msg, "reasoning", None) is not None:
            for thought_chunk in msg.reasoning:
                sys.stdout.write(f"[Thought] {thought_chunk}")
                sys.stdout.flush()

        # Stream visible response tokens in real-time
        collected_tokens: list[str] = []
        for delta in msg.text:
            text_str = str(delta)
            collected_tokens.append(text_str)
            sys.stdout.write(text_str)
            sys.stdout.flush()

        print("\n" + "-" * 70)

        full_content = "".join(collected_tokens).strip()
        ai_responses.append(AIMessage(content=full_content, name=persona_name))

    final_state = stream.output

    # Print Complete Debate Transcript from Graph Messages State
    print("\n" + "=" * 80)
    print("Complete Moderated Debate Transcript")
    print("=" * 80)

    recorded_messages = final_state.get("messages", []) if final_state else []
    for i, m in enumerate(recorded_messages, 1):
        sender = getattr(m, "name", None) or ("User" if isinstance(m, HumanMessage) else "System")
        text = _extract_text(m.content)
        print(f"\nEntry {i} - [{sender}]:")
        print(f"\"{text}\"")

    print("\n" + "=" * 80)
    print("Verification Summary")
    print("=" * 80)

    # Verify all messages in the final graph state
    assistant_msgs = [m for m in recorded_messages if isinstance(m, AIMessage)]
    speakers_seen = [getattr(m, "name", "Unknown") for m in assistant_msgs]
    print(f"Total assistant entries recorded: {len(assistant_msgs)}")
    print(f"Speaker sequence: {' -> '.join(speakers_seen)}")

    for i, res in enumerate(assistant_msgs, 1):
        text = _extract_text(res.content)
        word_count = len(text.split())
        print(f"  {i}. [{getattr(res, 'name', 'Unknown')}]: {word_count} words")
        assert len(text.strip()) > 0, f"Entry {i} by {getattr(res, 'name', 'Unknown')} produced empty response!"

    assert "Moderator" in speakers_seen, "Moderator did not participate in debate!"
    assert any(s != "Moderator" for s in speakers_seen), "No specialist personas participated in debate!"
    assert final_state is not None, "Graph execution did not produce final state!"

    print("\nEmpirical check PASSED: Moderator routed turns dynamically and produced final synthesis.")


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph Dynamic Moderated Debate (v3 Streaming Hub-and-Spoke)")
    parser.add_argument("--max-turns", type=int, default=6, help="Maximum number of participant turns (default: 6)")
    parser.add_argument("--topic", type=str, default=None, help="Philosophical topic to discuss")
    parser.add_argument(
        "--thinking",
        type=str,
        default="off",
        choices=["off", "low", "medium", "high"],
        help="Thinking/reasoning effort for local models (default: off for faster turns)",
    )
    args = parser.parse_args()

    run_moderated_debate(max_turns=args.max_turns, topic=args.topic, thinking=args.thinking)


if __name__ == "__main__":
    main()
