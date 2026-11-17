"""Specialized subagent definition for dynamic delegation."""

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel

from src.core.patterns.dynamic_delegation.state import DynamicDelegationState
from src.core.patterns.dynamic_delegation.tools import get_weather


def create_weather_subagent(model: BaseChatModel):
    """Instantiate a specialized weather child subagent with isolated context."""
    return create_agent(
        name="weather",
        model=model,
        system_prompt=(
            "You are a weather specialist. Always use get_weather to check real conditions. "
            "Execute tools sequentially and return a concise, factual report."
        ),
        tools=[get_weather],
        state_schema=DynamicDelegationState,
    )
