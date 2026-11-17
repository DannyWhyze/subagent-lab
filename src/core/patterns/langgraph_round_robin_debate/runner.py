"""Thin SSE streaming adapter for LangGraph Round-Robin 8-Persona Debate."""

import asyncio
import os
from collections.abc import AsyncGenerator

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

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
from src.core.patterns.langgraph_round_robin_debate.orchestration import (
    build_round_robin_debate_graph,
)
from src.core.patterns.langgraph_round_robin_debate.personas import PERSONA_BY_NODE


class LangGraphRoundRobinDebateRunner(BaseAgentRunner):
    """Deterministic cyclic round-robin debate runner using native LangGraph v3 streaming."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def _build_graph(self, thinking: str = "off"):
        reasoning_param: bool | str = (
            False if thinking == "off" else (True if thinking == "high" else thinking)
        )
        model = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=0.7,
            reasoning=reasoning_param,
        )
        return build_round_robin_debate_graph(model, max_rounds=8)

    async def run_stream(
        self, prompt: str, session_id: str, thinking: str = "off"
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        metrics = MetricsTracker()
        metrics.start()

        yield AgentStreamEvent(
            event_type="stage",
            payload=StagePayload(stage="debate_started", agent="coordinator").model_dump(),
        )

        final_answer = ""
        current_speaker: str | None = None

        try:
            graph = self._build_graph(thinking=thinking)
            initial_state = {
                "messages": [HumanMessage(content=f"Topic for discussion: {prompt}")],
                "current_round": 0,
                "max_rounds": 8,
            }

            stream = graph.stream_events(
                initial_state,
                version="v3",
                config={"recursion_limit": 50},
            )

            # Consume typed message generator
            for msg in stream.messages:
                node_id = getattr(msg, "node", "unknown")
                persona_info = PERSONA_BY_NODE.get(node_id, {})
                persona_name = persona_info.get("name", node_id.capitalize())

                if persona_name != current_speaker:
                    current_speaker = persona_name
                    yield AgentStreamEvent(
                        event_type="stage",
                        payload=StagePayload(stage=f"turn_{persona_name}", agent=persona_name).model_dump(),
                    )
                    await asyncio.sleep(0)

                # Stream reasoning tokens if active
                if getattr(msg, "reasoning", None) is not None:
                    for thought_chunk in msg.reasoning:
                        thought_str = str(thought_chunk)
                        if thinking != "off" and thought_str:
                            yield AgentStreamEvent(
                                event_type="thought",
                                payload=ThoughtPayload(delta=thought_str, source=persona_name).model_dump(),
                            )
                            await asyncio.sleep(0)

                # Stream text token deltas
                for delta in msg.text:
                    text_str = str(delta)
                    if text_str:
                        metrics.record_token()
                        final_answer += text_str
                        yield AgentStreamEvent(
                            event_type="token",
                            payload=TokenPayload(delta=text_str, source=persona_name).model_dump(),
                        )
                        await asyncio.sleep(0)

            yield AgentStreamEvent(
                event_type="done",
                payload=DonePayload(final_answer=final_answer).model_dump(),
            )

        except Exception as exc:
            yield AgentStreamEvent(
                event_type="error",
                payload=ErrorPayload(
                    message=f"LangGraph Round-Robin Debate error: {exc}",
                    code="LANGGRAPH_DEBATE_ERROR",
                ).model_dump(),
            )

        finally:
            yield AgentStreamEvent(
                event_type="metrics",
                payload=metrics.finish().model_dump(),
            )
