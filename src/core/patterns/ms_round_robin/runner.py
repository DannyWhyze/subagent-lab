"""Thin SSE streaming adapter for Microsoft Round-Robin GroupChat."""

import os
from collections.abc import AsyncGenerator

from agent_framework import AgentResponseUpdate

from src.core.base import BaseAgentRunner
from src.core.metrics import MetricsTracker
from src.core.models import (
    AgentStreamEvent,
    DonePayload,
    ErrorPayload,
    StagePayload,
    ThoughtPayload,
    TokenPayload,
)
from src.core.patterns.common.ms_client import OllamaCompatibleOpenAIChatClient
from src.core.patterns.ms_round_robin.orchestration import build_writer_reviewer_chat
from src.core.patterns.ms_round_robin.participants import (
    create_reviewer_agent,
    create_writer_agent,
)


class MSRoundRobinRunner(BaseAgentRunner):
    """Deterministic Round-Robin GroupChat orchestration (Writer-Reviewer loop)."""

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
            payload=StagePayload(stage="discourse_started", agent="coordinator").model_dump(),
        )

        effort = "none" if thinking == "off" else thinking
        default_options = {"reasoning": {"effort": effort}}

        client = self._build_client()
        writer = create_writer_agent(client, default_options=default_options)
        reviewer = create_reviewer_agent(client, default_options=default_options)
        workflow = build_writer_reviewer_chat([writer, reviewer], max_rounds=6)

        final_answer = ""
        current_speaker = None

        try:
            async for event in workflow.run(prompt, stream=True):
                ev_type = getattr(event, "type", None)

                # 1. GroupChat participant turn transitions
                if ev_type == "group_chat" and hasattr(event, "data"):
                    participant = getattr(event.data, "participant_name", None)
                    if participant and participant != current_speaker:
                        current_speaker = participant
                        yield AgentStreamEvent(
                            event_type="stage",
                            payload=StagePayload(stage=f"turn_{participant}", agent=participant).model_dump(),
                        )

                # 2. Process streaming intermediate chunks from active participant
                elif ev_type == "intermediate" and hasattr(event, "data"):
                    update = event.data
                    if isinstance(update, AgentResponseUpdate):
                        author = (
                            getattr(update, "author_name", None)
                            or getattr(event, "author_name", None)
                            or current_speaker
                            or "group_chat_orchestrator"
                        )
                        if author != current_speaker:
                            current_speaker = author
                            yield AgentStreamEvent(
                                event_type="stage",
                                payload=StagePayload(stage=f"turn_{author}", agent=author).model_dump(),
                            )

                        if update.contents:
                            for content in update.contents:
                                c_type = getattr(content, "type", None)
                                merge_mode = getattr(content, "merge_mode", "append")

                                # Thinking tokens
                                if c_type == "text_reasoning":
                                    r_text = getattr(content, "text", "")
                                    if r_text and thinking != "off" and merge_mode != "replace":
                                        yield AgentStreamEvent(
                                            event_type="thought",
                                            payload=ThoughtPayload(delta=r_text, source=author).model_dump(),
                                        )

                                # Answer text deltas (ignoring full-text 'replace' done chunks)
                                elif c_type == "text":
                                    text_delta = getattr(content, "text", "")
                                    if text_delta and merge_mode != "replace":
                                        metrics.record_token()
                                        final_answer += text_delta
                                        yield AgentStreamEvent(
                                            event_type="token",
                                            payload=TokenPayload(
                                                delta=text_delta, source=author
                                            ).model_dump(),
                                        )
                        elif update.text:
                            metrics.record_token()
                            final_answer += update.text
                            yield AgentStreamEvent(
                                event_type="token",
                                payload=TokenPayload(delta=update.text, source=author).model_dump(),
                            )

            yield AgentStreamEvent(
                event_type="done",
                payload=DonePayload(final_answer=final_answer).model_dump(),
            )

        except Exception as exc:
            yield AgentStreamEvent(
                event_type="error",
                payload=ErrorPayload(
                    message=f"Round-Robin GroupChat error: {exc}",
                    code="ROUND_ROBIN_ERROR",
                ).model_dump(),
            )

        finally:
            yield AgentStreamEvent(
                event_type="metrics",
                payload=metrics.finish().model_dump(),
            )
