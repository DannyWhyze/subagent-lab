"""Thin SSE streaming adapter for Hugging Face smolagents pattern."""

import asyncio
import json
import threading
from collections.abc import AsyncGenerator
from typing import Any

from smolagents import (
    ActionStep,
    ChatMessageStreamDelta,
    FinalAnswerStep,
    OpenAIServerModel,
)

from src.core.base import BaseAgentRunner
from src.core.metrics import MetricsTracker
from src.core.models import (
    AgentStreamEvent,
    DonePayload,
    ErrorPayload,
    StagePayload,
    SubagentPayload,
    TokenPayload,
    ToolCallPayload,
)
from src.core.patterns.smolagents.subagent import create_weather_specialist
from src.core.patterns.smolagents.supervisor import create_supervisor


class SmolagentsRunner(BaseAgentRunner):
    """Executes tasks using Hugging Face smolagents with hierarchical subagent delegation."""

    def __init__(
        self,
        model_name: str = "qwen3.5:latest",
        api_base: str = "http://localhost:11434/v1",
    ) -> None:
        self.model_name = model_name
        self.api_base = api_base

    def _create_model(self, thinking: str) -> OpenAIServerModel:
        """Instantiate OpenAIServerModel mapped to local Ollama with reasoning control."""
        effort = "none" if thinking == "off" else thinking
        return OpenAIServerModel(
            model_id=self.model_name,
            api_base=self.api_base,
            api_key="ollama",
            extra_body={"reasoning_effort": effort},
        )

    def _build_supervisor(self, model: OpenAIServerModel):
        weather_specialist = create_weather_specialist(model)
        return create_supervisor(model, managed_agents=[weather_specialist])

    async def run_stream(
        self, prompt: str, session_id: str, thinking: str = "off"
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        metrics = MetricsTracker()
        metrics.start()

        yield AgentStreamEvent(
            event_type="stage",
            payload=StagePayload(stage="smolagents_started", agent="supervisor").model_dump(),
        )

        model = self._create_model(thinking)
        supervisor = self._build_supervisor(model)

        queue: asyncio.Queue[Any] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def worker() -> None:
            """Synchronous thread runner pushing stream generator items into asyncio.Queue."""
            try:
                for step in supervisor.run(prompt, stream=True):
                    loop.call_soon_threadsafe(queue.put_nowait, step)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        worker_thread = threading.Thread(target=worker, daemon=True)
        worker_thread.start()

        final_answer_recorded: str | None = None

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item

                # 1. Text token streaming
                if isinstance(item, ChatMessageStreamDelta):
                    if item.content:
                        metrics.record_token()
                        yield AgentStreamEvent(
                            event_type="token",
                            payload=TokenPayload(delta=item.content, source="supervisor").model_dump(),
                        )

                # 2. Action / Tool execution steps
                elif isinstance(item, ActionStep):
                    if item.code_action:
                        code_str = item.code_action.strip()
                        if "weather_specialist" in code_str:
                            yield AgentStreamEvent(
                                event_type="subagent",
                                payload=SubagentPayload(
                                    name="weather_specialist",
                                    task=code_str,
                                ).model_dump(),
                            )

                        metrics.record_tool_call()
                        yield AgentStreamEvent(
                            event_type="tool_call",
                            payload=ToolCallPayload(
                                tool="code_interpreter",
                                input={"code": code_str},
                                output=str(item.observations) if item.observations else None,
                            ).model_dump(),
                        )

                    if item.tool_calls:
                        for tc in item.tool_calls:
                            tc_name = getattr(tc, "name", "tool")
                            tc_args = getattr(tc, "arguments", {})
                            if tc_name == "weather_specialist":
                                yield AgentStreamEvent(
                                    event_type="subagent",
                                    payload=SubagentPayload(
                                        name="weather_specialist",
                                        task=str(tc_args),
                                    ).model_dump(),
                                )
                            metrics.record_tool_call()
                            yield AgentStreamEvent(
                                event_type="tool_call",
                                payload=ToolCallPayload(
                                    tool=tc_name,
                                    input=tc_args if isinstance(tc_args, dict) else {"arg": str(tc_args)},
                                    output=str(item.observations) if item.observations else None,
                                ).model_dump(),
                            )

                # 3. Final answer step
                elif isinstance(item, FinalAnswerStep):
                    ans = item.output
                    if isinstance(ans, (dict, list)):
                        final_answer_recorded = json.dumps(ans, indent=2)
                    else:
                        final_answer_recorded = str(ans)

            if final_answer_recorded is not None:
                metrics.record_token()
                yield AgentStreamEvent(
                    event_type="token",
                    payload=TokenPayload(delta=final_answer_recorded, source="smolagents").model_dump(),
                )
                yield AgentStreamEvent(
                    event_type="done",
                    payload=DonePayload(final_answer=final_answer_recorded).model_dump(),
                )

        except Exception as exc:
            yield AgentStreamEvent(
                event_type="error",
                payload=ErrorPayload(
                    message=f"smolagents execution error: {exc}",
                    code="SMOLAGENTS_ERROR",
                ).model_dump(),
            )

        finally:
            yield AgentStreamEvent(
                event_type="metrics",
                payload=metrics.finish().model_dump(),
            )
