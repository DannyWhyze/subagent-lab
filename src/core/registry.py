"""Central registry for subagent architecture runners and metadata."""

import asyncio
from collections.abc import AsyncGenerator

from src.core.base import BaseAgentRunner
from src.core.metrics import MetricsTracker
from src.core.models import (
    AgentStreamEvent,
    DonePayload,
    PatternMetadata,
    StagePayload,
    SubagentPayload,
    ThoughtPayload,
    TokenPayload,
    ToolCallPayload,
)
from src.core.patterns.ast_code_agent import ASTCodeRunner
from src.core.patterns.dynamic_delegation import DynamicDelegationRunner
from src.core.patterns.langchain_subagent_tool import LangChainSubagentToolRunner
from src.core.patterns.langgraph_moderated_debate import LangGraphModeratedDebateRunner
from src.core.patterns.langgraph_round_robin_debate import LangGraphRoundRobinDebateRunner
from src.core.patterns.ms_agent_as_tool import MSAgentToolRunner
from src.core.patterns.ms_chess import MSChessRunner
from src.core.patterns.ms_moderated_debate import MSModeratedDebateRunner
from src.core.patterns.ms_round_robin import MSRoundRobinRunner
from src.core.patterns.ms_round_robin_debate import MSRoundRobinDebateRunner
from src.core.patterns.smolagents import SmolagentsRunner
from src.core.patterns.virtual_filesystem import DeepAgentFilesystemRunner
from src.core.session_store import SessionStore


class MockAgentRunner(BaseAgentRunner):
    """Deterministic offline runner for testing and verification without external LLMs."""

    def __init__(self, delay_ms: float = 5.0) -> None:
        self.delay = delay_ms / 1000.0

    async def run_stream(
        self, prompt: str, session_id: str, thinking: str = "off"
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        metrics = MetricsTracker()
        metrics.start()

        yield AgentStreamEvent(
            event_type="stage",
            payload=StagePayload(stage="mock_started", agent="mock_supervisor").model_dump(),
        )
        await asyncio.sleep(self.delay)

        thought_text = (
            "Evaluating offline test prompt and synthesizing execution plan."
            if thinking == "off"
            else "Mock reasoning and deep strategic consideration for multi-agent delegation."
        )
        yield AgentStreamEvent(
            event_type="thought",
            payload=ThoughtPayload(
                delta=thought_text,
                source="mock_supervisor",
            ).model_dump(),
        )
        await asyncio.sleep(self.delay * 2)

        yield AgentStreamEvent(
            event_type="subagent",
            payload=SubagentPayload(
                name="mock_subagent",
                task=f"Synthesize prompt: '{prompt}' with session: {session_id}",
            ).model_dump(),
        )
        await asyncio.sleep(self.delay)

        metrics.record_tool_call()
        yield AgentStreamEvent(
            event_type="tool_call",
            payload=ToolCallPayload(
                tool="mock_tool",
                input={"query": prompt},
                output="Mock tool execution successful.",
            ).model_dump(),
        )
        await asyncio.sleep(self.delay)

        response_tokens = [
            "Mock ",
            "response ",
            "for: ",
            f"'{prompt}'. ",
            "Subagent ",
            "context ",
            "isolated.",
        ]
        for token in response_tokens:
            metrics.record_token()
            yield AgentStreamEvent(
                event_type="token",
                payload=TokenPayload(delta=token, source="mock_supervisor").model_dump(),
            )
            await asyncio.sleep(self.delay)

        yield AgentStreamEvent(
            event_type="metrics",
            payload=metrics.finish().model_dump(),
        )

        yield AgentStreamEvent(
            event_type="done",
            payload=DonePayload(final_answer="".join(response_tokens)).model_dump(),
        )


class RunnerRegistry:
    """Registry maintaining active agent pattern runners and descriptive metadata."""

    def __init__(self) -> None:
        self.session_store = SessionStore()
        self._runners: dict[str, BaseAgentRunner] = {}
        self._metadata: dict[str, PatternMetadata] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        # 1. Dynamic Delegation Task Tool
        self.register(
            PatternMetadata(
                id="dynamic_delegation",
                name="Dynamic Delegation Task Tool",
                description="LangGraph v3 supervisor with isolated child subagent state via dynamic task meta-tool.",
                framework="LangChain / LangGraph",
                isolation_type="Caller-Callee (Private Subagent State)",
                example_prompts=[
                    "What is the weather in Berlin right now?",
                    "Check the weather in Tokyo and tell me if it is sunny.",
                ],
            ),
            DynamicDelegationRunner(),
        )

        # 2. Autonomous DeepAgent Virtual FS
        self.register(
            PatternMetadata(
                id="virtual_filesystem",
                name="DeepAgent Virtual Filesystem",
                description="Autonomous LangGraph DeepAgent with in-memory virtual state files and SessionStore caching.",
                framework="LangChain / LangGraph",
                isolation_type="Shared State Sandbox",
                example_prompts=[
                    "Research the Model Context Protocol (MCP) and write an overview report to disk.",
                    "Inspect the existing files on disk using ls and summarize what you find.",
                ],
            ),
            DeepAgentFilesystemRunner(session_store=self.session_store),
        )

        # 3. LangChain Subagent-as-Tool
        self.register(
            PatternMetadata(
                id="langchain_subagent_tool",
                name="LangChain Subagent-as-Tool",
                description="LangChain supervisor delegating to a weather specialist wrapped inside a standard function @tool.",
                framework="LangChain / LangGraph",
                isolation_type="Tool-Wrapped Agent (Isolated Invoke)",
                example_prompts=[
                    "Please ask the weather specialist for the current weather in Paris.",
                    "What are the weather conditions in Sydney?",
                ],
            ),
            LangChainSubagentToolRunner(),
        )

        # 4. Microsoft Agent Framework as_tool
        self.register(
            PatternMetadata(
                id="ms_agent_as_tool",
                name="Microsoft Agent as_tool",
                description="Microsoft Agent Framework supervisor with weather specialist encapsulated via agent.as_tool().",
                framework="Microsoft Agent Framework",
                isolation_type="Caller-Callee (propagate_session=False)",
                example_prompts=[
                    "Consult your weather specialist to get the forecast for London.",
                    "How warm is it in Rome right now?",
                ],
            ),
            MSAgentToolRunner(),
        )

        # 5. Microsoft Round-Robin GroupChat
        self.register(
            PatternMetadata(
                id="ms_round_robin",
                name="Microsoft Round-Robin GroupChat",
                description="Microsoft GroupChat orchestration with deterministic cyclic speaker selection (Writer & Reviewer).",
                framework="Microsoft Agent Framework",
                isolation_type="Mesh Discourse (Shared History)",
                example_prompts=[
                    "Explain Docker containers to a beginner in 3 sentences.",
                    "Draft a concise comparison between microservices and monoliths.",
                ],
            ),
            MSRoundRobinRunner(),
        )

        # 6. Microsoft Round-Robin 8-Persona Debate
        self.register(
            PatternMetadata(
                id="ms_round_robin_debate",
                name="MS Round-Robin 8-Persona Debate",
                description="Deterministic debate across 8 global cultural perspectives (Farmer, Dev, Teacher, Doctor, etc.).",
                framework="Microsoft Agent Framework",
                isolation_type="Cyclic Peer Mesh (8 Personas)",
                example_prompts=[
                    "What constitutes a good and meaningful life?",
                    "Should technological innovation prioritize economic growth or planetary sustainability?",
                ],
            ),
            MSRoundRobinDebateRunner(),
        )

        # 7. Microsoft LLM-Moderated 8-Persona Debate
        self.register(
            PatternMetadata(
                id="ms_moderated_debate",
                name="MS Moderated 8-Persona Debate",
                description="Dynamic panel discussion where an LLM moderator selects speakers and concludes with a synthesis.",
                framework="Microsoft Agent Framework",
                isolation_type="Dynamic Moderated Mesh (8 Personas)",
                example_prompts=[
                    "Can artificial intelligence possess genuine creativity or only mimicry?",
                    "How do individual freedom and societal duty balance in a modern democracy?",
                ],
            ),
            MSModeratedDebateRunner(),
        )

        # 8. LangGraph Round-Robin 8-Persona Debate
        self.register(
            PatternMetadata(
                id="langgraph_round_robin_debate",
                name="LangGraph Round-Robin 8-Persona Debate",
                description="Deterministic cyclic debate across 8 global cultural perspectives using LangGraph Graph API (START, nodes, conditional cycle edges, v3 streaming).",
                framework="LangChain / LangGraph",
                isolation_type="Cyclic Peer Mesh (8 Personas)",
                example_prompts=[
                    "What does a good life mean to you personally?",
                    "Should technological innovation prioritize economic growth or planetary sustainability?",
                ],
            ),
            LangGraphRoundRobinDebateRunner(),
        )

        # 9. LangGraph LLM-Moderated 8-Persona Debate
        self.register(
            PatternMetadata(
                id="langgraph_moderated_debate",
                name="LangGraph Moderated 8-Persona Debate",
                description="Hierarchical debate with central LLM moderator using Pydantic structured output routing (ModeratorDecision) and closing synthesis.",
                framework="LangChain / LangGraph",
                isolation_type="Dynamic Hub-and-Spoke Supervisor (8 Personas)",
                example_prompts=[
                    "Can technological progress coexist with ecological sustainability and social justice?",
                    "How do individual freedom and societal duty balance in a modern democracy?",
                ],
            ),
            LangGraphModeratedDebateRunner(),
        )

        # 10. Microsoft Conversational Chess
        self.register(
            PatternMetadata(
                id="ms_chess",
                name="MS Conversational Chess",
                description="Conversational chess match between two AI agents with deterministic python-chess rules and real-time board rendering.",
                framework="Microsoft Agent Framework",
                isolation_type="Game Turn Guardrail (Spectator & Interactive)",
                example_prompts=[
                    "spectator:4",
                    "spectator:8",
                ],
            ),
            MSChessRunner(session_store=self.session_store),
        )

        # 11. AST Sandbox Code-First Agent
        self.register(
            PatternMetadata(
                id="ast_code_agent",
                name="AST Sandbox Code Agent",
                description="Code-First Python agent generating executable code evaluated in an isolated in-memory AST sandbox.",
                framework="Custom AST Sandbox",
                isolation_type="In-Memory AST Whitelist (No Imports / No Dunders)",
                example_prompts=[
                    "Please check the weather for Berlin and Paris, and return a dictionary mapping city to weather.",
                    "Calculate the sum of weather queries for Munich, Tokyo, and Paris.",
                ],
            ),
            ASTCodeRunner(),
        )

        # 12. Hugging Face smolagents ManagedAgent
        self.register(
            PatternMetadata(
                id="smolagents_managed",
                name="smolagents ManagedAgent",
                description="Hugging Face smolagents with hierarchical supervisor delegating to a specialized weather subagent.",
                framework="Hugging Face smolagents",
                isolation_type="Hierarchical Code-First (Managed Subagent)",
                example_prompts=[
                    "Ask the weather specialist to check the weather in Tokyo and Sydney, then provide a concise summary.",
                    "Compare the weather in Berlin and London using the weather specialist.",
                ],
            ),
            SmolagentsRunner(),
        )

        # 13. Deterministic Mock Runner (Offline Testing)
        self.register(
            PatternMetadata(
                id="mock_runner",
                name="Deterministic Mock Runner",
                description="Fast offline test runner generating all event types without LLM/Ollama dependencies.",
                framework="Builtin Test Mock",
                isolation_type="Mock Sandbox",
                example_prompts=[
                    "Simulate a full subagent execution run.",
                    "Test multi-stage streaming pipeline with mock tool calls.",
                ],
            ),
            MockAgentRunner(),
        )

    def register(self, metadata: PatternMetadata, runner: BaseAgentRunner) -> None:
        self._metadata[metadata.id] = metadata
        self._runners[metadata.id] = runner

    def get_metadata(self) -> list[PatternMetadata]:
        return list(self._metadata.values())

    def get_runner(self, pattern_id: str) -> BaseAgentRunner | None:
        return self._runners.get(pattern_id)


# Global singleton registry
registry = RunnerRegistry()
