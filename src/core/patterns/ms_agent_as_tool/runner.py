"""Thin SSE streaming adapter for Microsoft Agent Framework as_tool pattern."""

import os
from collections.abc import AsyncGenerator
from typing import Any

from agent_framework import AgentResponseUpdate

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
from src.core.patterns.common.ms_client import OllamaCompatibleOpenAIChatClient
from src.core.patterns.ms_agent_as_tool.subagent import create_weather_subagent
from src.core.patterns.ms_agent_as_tool.supervisor import create_supervisor_agent


class MSAgentToolRunner(BaseAgentRunner):
    """Hierarchical Caller-Callee pattern using Microsoft Agent Framework agent.as_tool()."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    def _build_client(self) -> OllamaCompatibleOpenAIChatClient:
        return OllamaCompatibleOpenAIChatClient(
            model=self.model_name,
            base_url=self.base_url,
            api_key="ollama",
        )

    async def run_stream(
        self, prompt: str, session_id: str, thinking: str = "off"
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        metrics = MetricsTracker()
        metrics.start()

        yield AgentStreamEvent(
            event_type="stage",
            payload=StagePayload(stage="supervisor_start", agent="supervisor").model_dump(),
        )

        effort = "none" if thinking == "off" else thinking
        default_options = {"reasoning": {"effort": effort}}

        client = self._build_client()
        weather_subagent = create_weather_subagent(client, default_options=default_options)
        supervisor = create_supervisor_agent(client, weather_subagent, default_options=default_options)

        final_answer = ""
        active_calls: dict[str, tuple[str, dict[str, Any]]] = {}
        seen_calls: set[str] = set()
        emitted_tool_calls: set[str] = set()

        try:
            async for update in supervisor.run(prompt, stream=True):
                if isinstance(update, AgentResponseUpdate):
                    author = getattr(update, "author_name", "supervisor") or "supervisor"

                    if update.contents:
                        for content in update.contents:
                            c_type = getattr(content, "type", None)
                            merge_mode = getattr(content, "merge_mode", "append")

                            # 1. Reasoning content
                            if c_type == "text_reasoning":
                                r_text = getattr(content, "text", "")
                                if r_text and thinking != "off" and merge_mode != "replace":
                                    yield AgentStreamEvent(
                                        event_type="thought",
                                        payload=ThoughtPayload(
                                            delta=r_text,
                                            source=author,
                                        ).model_dump(),
                                    )

                            # 2. Tool call initiation
                            elif c_type == "function_call":
                                cid = (
                                    getattr(content, "call_id", None)
                                    or getattr(content, "id", None)
                                    or f"call_{len(seen_calls)}"
                                )
                                name = getattr(content, "name", None) or "query_weather"
                                args = (
                                    content.parse_arguments()
                                    if hasattr(content, "parse_arguments")
                                    else getattr(content, "arguments", {})
                                )
                                if not isinstance(args, dict):
                                    args = {"raw": str(args)}
                                active_calls[cid] = (name, args)

                                if cid not in seen_calls:
                                    seen_calls.add(cid)
                                    metrics.record_tool_call()
                                    if name == "query_weather":
                                        city = args.get("city", "unknown")
                                        yield AgentStreamEvent(
                                            event_type="subagent",
                                            payload=SubagentPayload(
                                                name="weather_specialist",
                                                task=f"Check weather in {city}",
                                            ).model_dump(),
                                        )

                            # 3. Tool call execution result
                            elif c_type == "function_result":
                                cid = (
                                    getattr(content, "call_id", None)
                                    or getattr(content, "id", None)
                                    or f"call_{len(emitted_tool_calls)}"
                                )
                                name, args = active_calls.get(cid, ("query_weather", {}))
                                res = getattr(content, "result", None)
                                output_str = str(res) if res is not None else None
                                yield AgentStreamEvent(
                                    event_type="tool_call",
                                    payload=ToolCallPayload(
                                        tool=name,
                                        input=args,
                                        output=output_str,
                                    ).model_dump(),
                                )
                                emitted_tool_calls.add(cid)

                            # 4. Answer text deltas (ignoring full-text 'replace' done chunks)
                            elif c_type == "text":
                                text_delta = getattr(content, "text", "")
                                if text_delta and merge_mode != "replace":
                                    metrics.record_token()
                                    final_answer += text_delta
                                    yield AgentStreamEvent(
                                        event_type="token",
                                        payload=TokenPayload(
                                            delta=text_delta,
                                            source=author,
                                        ).model_dump(),
                                    )

                    elif update.text:
                        metrics.record_token()
                        final_answer += update.text
                        yield AgentStreamEvent(
                            event_type="token",
                            payload=TokenPayload(
                                delta=update.text,
                                source=author,
                            ).model_dump(),
                        )

            # Fallback for any tool calls that completed without a separate function_result event
            for cid in seen_calls:
                if cid not in emitted_tool_calls:
                    name, args = active_calls.get(cid, ("query_weather", {}))
                    yield AgentStreamEvent(
                        event_type="tool_call",
                        payload=ToolCallPayload(
                            tool=name,
                            input=args,
                            output=None,
                        ).model_dump(),
                    )

            yield AgentStreamEvent(
                event_type="done",
                payload=DonePayload(final_answer=final_answer).model_dump(),
            )

        except Exception as exc:
            yield AgentStreamEvent(
                event_type="error",
                payload=ErrorPayload(
                    message=f"Microsoft Agent as_tool error: {exc}",
                    code="MS_AGENT_ERROR",
                ).model_dump(),
            )

        finally:
            yield AgentStreamEvent(
                event_type="metrics",
                payload=metrics.finish().model_dump(),
            )
