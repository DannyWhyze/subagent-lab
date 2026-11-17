"""Graph compilation and topology for LangGraph Moderated Debate."""

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from src.core.patterns.langgraph_moderated_debate.personas import (
    PERSONAS,
    create_moderator_node,
    create_persona_node,
)
from src.core.patterns.langgraph_moderated_debate.state import ModeratedDebateState


def build_moderated_debate_graph(model: ChatOllama, max_rounds: int = 6):
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

    # 4. Conditional edge: Moderator routes dynamically to the selected participant or END
    possible_targets = [p["node"] for p in PERSONAS] + [END]
    builder.add_conditional_edges(
        "moderator",
        lambda state: state["next_speaker"],
        possible_targets,
    )

    # 5. Hub-and-spoke return edges: Every participant returns control to the moderator
    for persona_def in PERSONAS:
        builder.add_edge(persona_def["node"], "moderator")

    return builder.compile()
