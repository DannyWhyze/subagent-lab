"""Base interfaces and abstract contracts for agent runners."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from src.core.models import AgentStreamEvent


class BaseAgentRunner(ABC):
    """Abstract base class for all subagent pattern runners."""

    @abstractmethod
    async def run_stream(
        self, prompt: str, session_id: str, thinking: str = "off"
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        """Execute the agent workflow and stream events asynchronously.

        Args:
            prompt: User input prompt or task.
            session_id: Client session identifier.
            thinking: Reasoning effort level ('off', 'low', 'medium', 'high').

        Yields:
            AgentStreamEvent instances representing the progression of the agent workflow.
        """
