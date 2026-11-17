"""Supervisor agent factory for LangChain Subagent-as-Tool pattern."""

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool


def create_supervisor_agent(model: BaseChatModel, query_weather_tool: BaseTool):
    """Instantiate supervisor agent consuming subagent wrapped inside query_weather tool."""
    return create_agent(
        name="supervisor",
        model=model,
        tools=[query_weather_tool],
        system_prompt=(
            "You are a helpful supervisor coordinating user inquiries.\n"
            "Rules:\n"
            "1. When asked about weather conditions, invoke `query_weather` immediately.\n"
            "2. Do not emit conversational preamble or preliminary remarks before calling tools. Call the tool first.\n"
            "3. Always execute tools sequentially one at a time.\n"
            "4. Synthesize the final answer clearly for the user."
        ),
    )
