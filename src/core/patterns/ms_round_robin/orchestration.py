"""Orchestration logic and round-robin selection for Microsoft GroupChat."""

from agent_framework import Agent
from agent_framework.orchestrations import GroupChatBuilder
from agent_framework_orchestrations._group_chat import GroupChatState


def round_robin_selection(state: GroupChatState) -> str:
    """Cyclic deterministic speaker selection based on round number."""
    participant_names = list(state.participants.keys())
    return participant_names[state.current_round % len(participant_names)]


def build_writer_reviewer_chat(participants: list[Agent], max_rounds: int = 6):
    """Build GroupChat workflow terminating upon Reviewer approval."""
    return (
        GroupChatBuilder(
            participants=participants,
            selection_func=round_robin_selection,
            max_rounds=max_rounds,
            intermediate_output_from="all",
        )
        .with_termination_condition(
            lambda messages: any(
                "APPROVE" in (msg.text or "") for msg in messages if msg.author_name == "Reviewer"
            )
        )
        .build()
    )
