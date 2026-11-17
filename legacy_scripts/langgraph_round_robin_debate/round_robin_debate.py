"""Sample: Philosophical Debate using LangGraph Deterministic Round-Robin Orchestration.

This script implements the 8-persona philosophical debate according to official
LangGraph Graph API standards (Nodes, Explicit Edges, and v3 Content-Block Event Streaming).

Reference Documentation:
- Graph API Nodes: https://docs.langchain.com/oss/python/langgraph/graph-api-nodes
- v3 Streaming: stream_events(..., version="v3") via GraphRunStream / stream.messages
"""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, MessagesState, StateGraph

# Enforce Windows UTF-8 console output per AGENTS.md rules
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()


class RoundRobinDebateState(MessagesState):
    """Debate state tracking conversation messages and cyclical round counter."""

    current_round: int = 0
    max_rounds: int = 8


# Explicit specification of the 8 diverse global perspectives
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
                sanitized.append(HumanMessage(content=f"[{author}]: {msg.content}"))
            else:
                sanitized.append(msg)
        else:
            sanitized.append(msg)
    return sanitized


def create_persona_node(persona_def: dict[str, str], model: ChatOllama):
    """Standard LangGraph node function per Graph API specifications.

    Takes application state as input, invokes the underlying LLM, and returns
    a state update dict with the appended message and incremented round counter.
    """
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


def make_turn_router(next_node: str):
    """Conditional edge router verifying whether maximum turns have been reached."""

    def route_condition(state: RoundRobinDebateState) -> str:
        current = state.get("current_round", 0)
        max_r = state.get("max_rounds", 8)
        if current >= max_r:
            return END
        return next_node

    return route_condition


def build_round_robin_debate_graph(model: ChatOllama):
    """Compile the LangGraph cyclic round-robin state graph with explicit nodes and edges.

    Graph Topology:
      START -> farmer -> developer -> teacher -> activist ->
      spiritual_leader -> artist -> immigrant -> doctor -> (farmer | END)
    """
    builder = StateGraph(RoundRobinDebateState)

    # 1. Explicitly register each persona as a discrete node
    for persona_def in PERSONAS:
        node_name = persona_def["node"]
        builder.add_node(node_name, create_persona_node(persona_def, model))

    # 2. Explicit initial entrypoint edge
    builder.add_edge(START, "farmer")

    # 3. Explicit sequential and conditional transitions between all nodes
    for persona_def in PERSONAS:
        current_node = persona_def["node"]
        next_node = persona_def["next"]
        builder.add_conditional_edges(
            current_node,
            make_turn_router(next_node),
            [next_node, END],
        )

    return builder.compile()


def run_debate(max_turns: int = 8, topic: str | None = None, thinking: str = "off") -> None:
    """Execute the multi-agent debate using native LangGraph v3 stream_events."""
    if topic is None:
        topic = "What does a good life mean to you personally?"

    model_name = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    reasoning_param: bool | str = False if thinking == "off" else (True if thinking == "high" else thinking)

    print("=" * 80)
    print("LangGraph Multi-Agent Round-Robin Philosophical Debate (v3 Streaming)")
    print("=" * 80)
    print(f"Model: {model_name} @ {base_url}")
    print(f"Topic: '{topic}'")
    print(f"Configured Turns: {max_turns}")
    print(f"Thinking Mode: {thinking}")
    print("=" * 80)

    model = ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.7,
        reasoning=reasoning_param,
    )

    graph = build_round_robin_debate_graph(model)

    initial_state = {
        "messages": [HumanMessage(content=f"Topic for discussion: {topic}")],
        "current_round": 0,
        "max_rounds": max_turns,
    }

    # Opt-in to official LangGraph version="v3" event streaming
    stream = graph.stream_events(
        initial_state,
        version="v3",
        config={"recursion_limit": max(50, max_turns * 3)},
    )

    ai_responses: list[AIMessage] = []

    # Stream model messages via stream.messages typed projection
    for msg in stream.messages:
        node_id = getattr(msg, "node", "unknown")
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

    # Print Full Final Transcript and Verification Summary
    print("\n" + "=" * 80)
    print("Complete Debate Transcript")
    print("=" * 80)

    for i, res in enumerate(ai_responses, 1):
        print(f"\nTurn {i} - [{res.name}]:")
        print(f"\"{res.content}\"")

    print("\n" + "=" * 80)
    print("Verification Summary")
    print("=" * 80)

    speakers_seen = [getattr(m, "name", "Unknown") for m in ai_responses]
    print(f"Total AI turns executed: {len(ai_responses)}")
    print(f"Speaker sequence: {' -> '.join(speakers_seen)}")

    for i, res in enumerate(ai_responses, 1):
        word_count = len(str(res.content).split())
        print(f"  {i}. [{res.name}]: {word_count} words")
        assert len(str(res.content).strip()) > 0, f"Speaker {res.name} produced empty response!"

    assert len(speakers_seen) == max_turns, (
        f"Expected {max_turns} turns, but recorded {len(speakers_seen)}!"
    )
    assert final_state is not None, "Graph execution did not produce final state!"

    print("\nEmpirical check PASSED: All participants streamed live and spoke in sequence.")


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph Round-Robin Philosophical Debate (v3 Streaming)")
    parser.add_argument("--max-turns", type=int, default=8, help="Maximum number of turns (default: 8)")
    parser.add_argument("--topic", type=str, default=None, help="Philosophical topic to discuss")
    parser.add_argument(
        "--thinking",
        type=str,
        default="off",
        choices=["off", "low", "medium", "high"],
        help="Thinking/reasoning effort for local models (default: off for faster turns)",
    )
    args = parser.parse_args()

    run_debate(max_turns=args.max_turns, topic=args.topic, thinking=args.thinking)


if __name__ == "__main__":
    main()
