"""Thin SSE streaming adapter for AST Code-First Agent."""

import json
from collections.abc import AsyncGenerator

from langchain_ollama import ChatOllama

from src.core.base import BaseAgentRunner
from src.core.metrics import MetricsTracker
from src.core.models import (
    AgentStreamEvent,
    CodePayload,
    DonePayload,
    ErrorPayload,
    StagePayload,
    ThoughtPayload,
    TokenPayload,
    ToolCallPayload,
)
from src.core.patterns.ast_code_agent.agent import SYSTEM_PROMPT, extract_python_code
from src.core.patterns.ast_code_agent.sandbox import ASTSandbox
from src.core.patterns.ast_code_agent.tools import get_weather


class ASTCodeRunner(BaseAgentRunner):
    """Executes problems using a Code-First paradigm evaluated inside an AST Sandbox."""

    def __init__(
        self,
        model_name: str = "qwen3.5:latest",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url

    async def run_stream(
        self, prompt: str, session_id: str, thinking: str = "off"
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        metrics = MetricsTracker()
        metrics.start()

        yield AgentStreamEvent(
            event_type="stage",
            payload=StagePayload(stage="code_generation", agent="ast_code_agent").model_dump(),
        )

        reasoning_mode = thinking != "off"
        llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=0.0,
            reasoning=reasoning_mode,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        full_response = ""

        try:
            async for chunk in llm.astream(messages):
                reasoning_delta = getattr(chunk, "reasoning", None)
                if reasoning_delta and thinking != "off":
                    yield AgentStreamEvent(
                        event_type="thought",
                        payload=ThoughtPayload(delta=reasoning_delta, source="ast_code_agent").model_dump(),
                    )

                content_delta = chunk.content
                if isinstance(content_delta, str) and content_delta:
                    metrics.record_token()
                    full_response += content_delta
                    yield AgentStreamEvent(
                        event_type="code",
                        payload=CodePayload(delta=content_delta, source="ast_code_agent").model_dump(),
                    )

            # Stage transition to AST Execution
            yield AgentStreamEvent(
                event_type="stage",
                payload=StagePayload(stage="ast_execution", agent="ast_sandbox").model_dump(),
            )

            code = extract_python_code(full_response)
            intercepted_tool_events: list[AgentStreamEvent] = []

            def monitored_weather(city: str) -> str:
                metrics.record_tool_call()
                result_str = get_weather(city)
                intercepted_tool_events.append(
                    AgentStreamEvent(
                        event_type="tool_call",
                        payload=ToolCallPayload(
                            tool="get_weather",
                            input={"city": city},
                            output=result_str,
                        ).model_dump(),
                    )
                )
                return result_str

            sandbox = ASTSandbox(tools={"get_weather": monitored_weather})
            exec_result = sandbox.execute(code)

            for tool_event in intercepted_tool_events:
                yield tool_event

            metrics.record_tool_call()
            yield AgentStreamEvent(
                event_type="tool_call",
                payload=ToolCallPayload(
                    tool="ast_sandbox",
                    input={"code": code},
                    output=f"Executed. Answer: {exec_result['final_answer']}",
                ).model_dump(),
            )

            final_ans = exec_result.get("final_answer")
            if final_ans is None:
                final_str = full_response
            elif isinstance(final_ans, (dict, list)):
                final_str = json.dumps(final_ans, indent=2, ensure_ascii=False)
            else:
                final_str = str(final_ans)

            # Emit synthesized final answer tokens as assistant response
            metrics.record_token()
            yield AgentStreamEvent(
                event_type="token",
                payload=TokenPayload(delta=final_str, source="ast_code_agent").model_dump(),
            )

            yield AgentStreamEvent(
                event_type="done",
                payload=DonePayload(final_answer=final_str).model_dump(),
            )

        except Exception as exc:
            yield AgentStreamEvent(
                event_type="error",
                payload=ErrorPayload(
                    message=f"AST Code Agent execution error: {exc}",
                    code="AST_AGENT_ERROR",
                ).model_dump(),
            )

        finally:
            yield AgentStreamEvent(
                event_type="metrics",
                payload=metrics.finish().model_dump(),
            )
