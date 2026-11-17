"""Round-robin orchestration for Microsoft 8-persona philosophical debate."""

from agent_framework import Agent
from agent_framework.orchestrations import GroupChatBuilder
from agent_framework_orchestrations._group_chat import GroupChatState


def round_robin_selection(state: GroupChatState) -> str:
    """Cyclic deterministic speaker selection based on round number."""
    participant_names = list(state.participants.keys())
    return participant_names[state.current_round % len(participant_names)]


def build_round_robin_debate(participants: list[Agent], max_rounds: int = 8):
    """Build GroupChat workflow iterating deterministically through all personas."""
    return GroupChatBuilder(
        participants=participants,
        selection_func=round_robin_selection,
        max_rounds=max_rounds,
        intermediate_output_from="all",
    ).build()
