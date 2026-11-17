"""Agent personas for conversational chess players."""

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient


def create_white_agent(client: OpenAIChatClient) -> Agent:
    """Instantiate competitive White Attacker chess agent."""
    return Agent(
        name="White_Attacker",
        instructions=(
            "You are a competitive chess master playing White. "
            "You prefer aggressive, dynamic piece activity, pawn breaks, and initiative. "
            "Always pick one move strictly from the provided legal moves list and justify it concisely."
        ),
        client=client,
    )


def create_black_agent(client: OpenAIChatClient) -> Agent:
    """Instantiate master Black Strategist chess agent."""
    return Agent(
        name="Black_Strategist",
        instructions=(
            "You are a master strategist playing Black. "
            "You value king safety, solid piece harmony, and counter-attacks. "
            "Always pick one move strictly from the provided legal moves list and justify it concisely."
        ),
        client=client,
    )
