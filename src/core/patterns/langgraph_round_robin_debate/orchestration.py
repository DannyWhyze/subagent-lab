"""Graph compilation and topology for LangGraph Round-Robin Philosophical Debate."""

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from src.core.patterns.langgraph_round_robin_debate.personas import (
    PERSONAS,
    create_persona_node,
)
from src.core.patterns.langgraph_round_robin_debate.state import RoundRobinDebateState


def make_turn_router(next_node: str):
    """Conditional edge router verifying whether configured maximum turns have been reached."""

    def route_condition(state: RoundRobinDebateState) -> str:
        current = state.get("current_round", 0)
        max_r = state.get("max_rounds", 8)
        if current >= max_r:
            return END
        return next_node

    return route_condition


def build_round_robin_debate_graph(model: ChatOllama, max_rounds: int = 8):
    """Compile the LangGraph cyclic round-robin state graph with explicit nodes and edges.

    Graph Topology:
      START -> farmer -> developer -> teacher -> activist ->
      spiritual_leader -> artist -> immigrant -> doctor -> (farmer | END)
    """
    builder = StateGraph(RoundRobinDebateState)

    # 1. Register each persona as a discrete node
    for persona_def in PERSONAS:
        node_name = persona_def["node"]
        builder.add_node(node_name, create_persona_node(persona_def, model))

    # 2. Initial entrypoint edge
    builder.add_edge(START, "farmer")

    # 3. Sequential and conditional transitions between all nodes
    for persona_def in PERSONAS:
        current_node = persona_def["node"]
        next_node = persona_def["next"]
        builder.add_conditional_edges(
            current_node,
            make_turn_router(next_node),
            [next_node, END],
        )

    return builder.compile()
