"""State schema and Pydantic structured output for LangGraph Moderated Debate."""

from typing import Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


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
