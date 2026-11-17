"""State schema for LangGraph Round-Robin Philosophical Debate."""

from langgraph.graph import MessagesState


class RoundRobinDebateState(MessagesState):
    """Debate state tracking conversation messages and cyclical round counter."""

    current_round: int = 0
    max_rounds: int = 8
