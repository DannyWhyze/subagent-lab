"""Thin SSE streaming adapter for dynamic delegation pattern."""

import os
from collections.abc import AsyncGenerator

from langchain_ollama import ChatOllama

from src.core.base import BaseAgentRunner
from src.core.metrics import MetricsTracker
from src.core.models import (
    AgentStreamEvent,
    DonePayload,
    ErrorPayload,
    StagePayload,
    SubagentPayload,
    ThoughtPayload,
    TokenPayload,
    ToolCallPayload,
)
from src.core.patterns.dynamic_delegation.subagent import create_weather_subagent
from src.core.patterns.dynamic_delegation.supervisor import create_supervisor_agent
from src.core.patterns.dynamic_delegation.task_tool import create_task_tool


class DynamicDelegationRunner(BaseAgentRunner):
    """Dynamic delegation using a custom task meta-tool and LangGraph v3 streaming."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def _build_agent(self, thinking: str = "off"):
        reasoning_val = False if thinking == "off" else (True if thinking == "high" else thinking)
        model = ChatOllama(model=self.model_name, base_url=self.base_url, reasoning=reasoning_val)
        weather_subagent = create_weather_subagent(model)
        task_tool = create_task_tool({"weather": weather_subagent})
        return create_supervisor_agent(model, task_tool)

    async def run_stream(
        self, prompt: str, session_id: str, thinking: str = "off"
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        metrics = MetricsTracker()
        metrics.start()
        full_response = []

        yield AgentStreamEvent(
            event_type="stage",
            payload=StagePayload(stage="supervisor_start", agent="supervisor").model_dump(),
        )

        try:
            agent = self._build_agent(thinking=thinking)
            stream = agent.stream_events(
                {"messages": [{"role": "user", "content": prompt}]},
                version="v3",
            )

            for kind, item in stream.interleave("messages", "tool_calls"):
                if kind == "messages":
                    if getattr(item, "reasoning", None) is not None:
                        for r_token in item.reasoning:
                            yield AgentStreamEvent(
                                event_type="thought",
                                payload=ThoughtPayload(delta=r_token, source="supervisor").model_dump(),
                            )
                    for token in item.text:
                        metrics.record_token()
                        full_response.append(token)
                        yield AgentStreamEvent(
                            event_type="token",
                            payload=TokenPayload(delta=token, source="supervisor").model_dump(),
                        )
                elif kind == "tool_calls":
                    metrics.record_tool_call()
                    tool_name = getattr(item, "tool_name", "")
                    tool_input = getattr(item, "input", {})
                    if not isinstance(tool_input, dict):
                        tool_input = {"raw": str(tool_input)}

                    if tool_name == "task":
                        yield AgentStreamEvent(
                            event_type="subagent",
                            payload=SubagentPayload(
                                name=tool_input.get("subagent_type", "weather"),
                                task=tool_input.get("description", ""),
                            ).model_dump(),
                        )

                    # AGENTS.md rule: Drain ToolCallStream channel completely
                    if hasattr(item, "__iter__"):
                        for _ in item:
                            pass

                    tool_output = getattr(item, "output", None)
                    yield AgentStreamEvent(
                        event_type="tool_call",
                        payload=ToolCallPayload(
                            tool=tool_name,
                            input=tool_input,
                            output=str(tool_output) if tool_output is not None else None,
                        ).model_dump(),
                    )

            final_text = "".join(full_response)
            yield AgentStreamEvent(
                event_type="metrics",
                payload=metrics.finish().model_dump(),
            )
            yield AgentStreamEvent(
                event_type="done",
                payload=DonePayload(final_answer=final_text).model_dump(),
            )

        except Exception as exc:
            yield AgentStreamEvent(
                event_type="error",
                payload=ErrorPayload(
                    message=f"Dynamic delegation execution error: {exc}",
                    code="DELEGATION_ERROR",
                ).model_dump(),
            )
