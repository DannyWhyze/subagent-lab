"""Participant agents for Microsoft GroupChat Round-Robin pattern."""

from typing import Any

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient


def create_writer_agent(
    client: OpenAIChatClient,
    default_options: dict[str, Any] | None = None,
) -> Agent:
    """Instantiate technical writer participant agent."""
    return Agent(
        name="Writer",
        description="Technical writer drafting concise explanations.",
        instructions=(
            "You are a technical writer. When given a task or critique, write or refine the explanation. "
            "Keep drafts concise, precise, and professional (under 4 sentences)."
        ),
        client=client,
        default_options=default_options,
    )


def create_reviewer_agent(
    client: OpenAIChatClient,
    default_options: dict[str, Any] | None = None,
) -> Agent:
    """Instantiate quality reviewer participant agent."""
    return Agent(
        name="Reviewer",
        description="Quality reviewer who critiques drafts and gives final approval.",
        instructions=(
            "You are a quality reviewer. Review the draft provided by the Writer. "
            "If it meets quality standards, end your response with the exact word: APPROVE. "
            "If improvements are needed, give 1-2 specific suggestions for revision."
        ),
        client=client,
        default_options=default_options,
    )
