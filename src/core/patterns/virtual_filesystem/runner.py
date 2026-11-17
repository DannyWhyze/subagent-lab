"""Thin SSE streaming adapter for Autonomous DeepAgent with virtual filesystem."""

import os
from collections.abc import AsyncGenerator
from typing import Any

from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver

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
from src.core.patterns.virtual_filesystem.file_tools import ls, read_file, write_file
from src.core.patterns.virtual_filesystem.research_tools import think_tool, web_search
from src.core.patterns.virtual_filesystem.subagent import create_research_subagent
from src.core.patterns.virtual_filesystem.supervisor import create_deep_agent_supervisor
from src.core.patterns.virtual_filesystem.task_tool import create_research_task_tool
from src.core.session_store import SessionStore


class DeepAgentFilesystemRunner(BaseAgentRunner):
    """Autonomous DeepAgent using a virtual state filesystem and InMemorySaver checkpointer."""

    def __init__(self, session_store: SessionStore, model_name: str | None = None) -> None:
        self.session_store = session_store
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:latest")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.checkpointer = InMemorySaver()

    def _build_agent(self, thinking: str = "off"):
        reasoning_val = False if thinking == "off" else (True if thinking == "high" else thinking)
        model = ChatOllama(model=self.model_name, base_url=self.base_url, reasoning=reasoning_val)
        subagent_tools = [web_search, think_tool, write_file, read_file, ls]
        research_subagent = create_research_subagent(model, subagent_tools)
        task_tool = create_research_task_tool({"research-agent": research_subagent})
        supervisor_tools = [task_tool, ls, read_file, write_file, think_tool]
        return create_deep_agent_supervisor(model, supervisor_tools, checkpointer=self.checkpointer)

    async def run_stream(
        self, prompt: str, session_id: str, thinking: str = "off"
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        metrics = MetricsTracker()
        metrics.start()
        full_response = []

        yield AgentStreamEvent(
            event_type="stage",
            payload=StagePayload(stage="fs_supervisor_start", agent="supervisor").model_dump(),
        )

        try:
            # Restore virtual files from session store if present
            existing_session = self.session_store.get(session_id) or {}
            existing_files = existing_session.get("files", {})

            agent = self._build_agent(thinking=thinking)
            initial_state: dict[str, Any] = {
                "messages": [{"role": "user", "content": prompt}],
            }
            if existing_files:
                initial_state["files"] = existing_files

            config = {"configurable": {"thread_id": session_id}}
            stream = agent.stream_events(initial_state, config=config, version="v3")
            latest_files = dict(existing_files)

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
                                name=tool_input.get("subagent_type", "research-agent"),
                                task=tool_input.get("description", ""),
                            ).model_dump(),
                        )

                    # AGENTS.md rule: Drain ToolCallStream channel
                    if hasattr(item, "__iter__"):
                        for _ in item:
                            pass

                    tool_output = getattr(item, "output", None)
                    # If write_file was called, update files cache
                    if tool_name == "write_file" and "file_path" in tool_input and "content" in tool_input:
                        latest_files[tool_input["file_path"]] = tool_input["content"]

                    yield AgentStreamEvent(
                        event_type="tool_call",
                        payload=ToolCallPayload(
                            tool=tool_name,
                            input=tool_input,
                            output=str(tool_output) if tool_output is not None else None,
                        ).model_dump(),
                    )

            # Persist virtual files back to session store
            self.session_store.set(session_id, {"files": latest_files})

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
                    message=f"DeepAgentFS execution error: {exc}",
                    code="FILESYSTEM_ERROR",
                ).model_dump(),
            )
