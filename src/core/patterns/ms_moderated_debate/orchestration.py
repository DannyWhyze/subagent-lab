"""Dynamic LLM-moderated orchestration for Microsoft 8-persona philosophical debate."""

from agent_framework import Agent
from agent_framework.orchestrations import GroupChatBuilder


def build_moderated_debate(moderator: Agent, participants: list[Agent], max_turns: int = 8):
    """Build GroupChat workflow with dynamic orchestrator agent."""
    return (
        GroupChatBuilder(
            participants=participants,
            intermediate_output_from="all",
            orchestrator_agent=moderator,
        )
        .with_termination_condition(
            lambda messages: sum(1 for msg in messages if msg.role == "assistant") >= max_turns
        )
        .build()
    )
