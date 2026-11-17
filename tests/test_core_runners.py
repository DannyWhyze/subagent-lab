"""Unit tests for core schemas, session storage, metrics, and runner registry."""

import inspect
from typing import Any

import pytest
from agent_framework import AgentResponseUpdate, Content
from pydantic import ValidationError

from src.core.metrics import MetricsTracker
from src.core.models import AgentStreamEvent, ChessBoardPayload, CodePayload, StreamRequest
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
from src.core.registry import MockAgentRunner, registry
from src.core.session_store import SessionStore


def test_stream_request_validation():
    # Valid request
    req = StreamRequest(
        pattern_id="dynamic_delegation",
        session_id="sess_12345",
        prompt="Explain subagents",
    )
    assert req.pattern_id == "dynamic_delegation"
    assert req.session_id == "sess_12345"
    assert req.prompt == "Explain subagents"

    # Invalid pattern_id (special chars, path traversal attempt)
    with pytest.raises(ValidationError):
        StreamRequest(
            pattern_id="../../hack",
            session_id="sess_12345",
            prompt="Hello",
        )

    # Invalid session_id (special chars)
    with pytest.raises(ValidationError):
        StreamRequest(
            pattern_id="dynamic_delegation",
            session_id="sess;rm -rf",
            prompt="Hello",
        )

    # Empty prompt
    with pytest.raises(ValidationError):
        StreamRequest(
            pattern_id="dynamic_delegation",
            session_id="sess_12345",
            prompt="",
        )

    # Overly long prompt (>4000 characters)
    with pytest.raises(ValidationError):
        StreamRequest(
            pattern_id="dynamic_delegation",
            session_id="sess_12345",
            prompt="a" * 4001,
        )


def test_session_store_lru_eviction():
    store = SessionStore(max_sessions=3)

    store.set("sess1", {"data": 1})
    store.set("sess2", {"data": 2})
    store.set("sess3", {"data": 3})
    assert len(store) == 3

    # Access sess1 to mark it recently used
    assert store.get("sess1") == {"data": 1}

    # Add sess4 -> sess2 should be evicted (as sess1 was moved to end)
    store.set("sess4", {"data": 4})
    assert len(store) == 3
    assert store.get("sess2") is None
    assert store.get("sess1") == {"data": 1}
    assert store.get("sess3") == {"data": 3}
    assert store.get("sess4") == {"data": 4}

    # Delete
    assert store.delete("sess3") is True
    assert store.get("sess3") is None
    assert len(store) == 2

    # Clear
    store.clear()
    assert len(store) == 0


def test_metrics_tracker():
    tracker = MetricsTracker()
    tracker.start()
    assert tracker.token_count == 0
    assert tracker.tool_calls == 0

    tracker.record_tool_call()
    tracker.record_tool_call()
    assert tracker.tool_calls == 2

    tracker.record_token(5)
    assert tracker.token_count == 5
    assert tracker.get_ttft_ms() >= 0.0

    payload = tracker.finish()
    assert payload.token_count == 5
    assert payload.tool_calls == 2
    assert payload.total_duration_ms >= 0.0


@pytest.mark.asyncio
async def test_mock_agent_runner_stream():
    runner = MockAgentRunner(delay_ms=1.0)
    events = []

    async for event in runner.run_stream(prompt="Test prompt", session_id="test_sess"):
        events.append(event)

    event_types = [e.event_type for e in events]
    assert "stage" in event_types
    assert "subagent" in event_types
    assert "tool_call" in event_types
    assert "token" in event_types
    assert "metrics" in event_types
    assert "done" in event_types

    done_event = next(e for e in events if e.event_type == "done")
    assert "Test prompt" in done_event.payload["final_answer"]


def test_runner_registry():
    metadata_list = registry.get_metadata()
    pattern_ids = [m.id for m in metadata_list]
    assert "dynamic_delegation" in pattern_ids
    assert "virtual_filesystem" in pattern_ids
    assert "langchain_subagent_tool" in pattern_ids
    assert "ms_agent_as_tool" in pattern_ids
    assert "ms_round_robin" in pattern_ids
    assert "ms_round_robin_debate" in pattern_ids
    assert "ms_moderated_debate" in pattern_ids
    assert "langgraph_round_robin_debate" in pattern_ids
    assert "langgraph_moderated_debate" in pattern_ids
    assert "ms_chess" in pattern_ids
    assert "ast_code_agent" in pattern_ids
    assert "smolagents_managed" in pattern_ids
    assert "mock_runner" in pattern_ids

    runner = registry.get_runner("mock_runner")
    assert isinstance(runner, MockAgentRunner)

    ast_runner = registry.get_runner("ast_code_agent")
    assert isinstance(ast_runner, ASTCodeRunner)

    smol_runner = registry.get_runner("smolagents_managed")
    assert isinstance(smol_runner, SmolagentsRunner)

    lc_runner = registry.get_runner("langchain_subagent_tool")
    assert isinstance(lc_runner, LangChainSubagentToolRunner)

    rr_debate = registry.get_runner("ms_round_robin_debate")
    assert isinstance(rr_debate, MSRoundRobinDebateRunner)

    mod_debate = registry.get_runner("ms_moderated_debate")
    assert isinstance(mod_debate, MSModeratedDebateRunner)

    lg_rr = registry.get_runner("langgraph_round_robin_debate")
    assert isinstance(lg_rr, LangGraphRoundRobinDebateRunner)

    lg_mod = registry.get_runner("langgraph_moderated_debate")
    assert isinstance(lg_mod, LangGraphModeratedDebateRunner)

    chess_runner = registry.get_runner("ms_chess")
    assert isinstance(chess_runner, MSChessRunner)

    non_existent = registry.get_runner("non_existent_id")
    assert non_existent is None


def test_chess_board_payload_serialization():
    payload = ChessBoardPayload(
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        turn=1,
        current_player="White",
        last_move="e2e4",
        san="e4",
        thought="Control the center",
        is_check=False,
        is_game_over=False,
    )
    event = AgentStreamEvent(event_type="chess_board", payload=payload.model_dump())
    assert event.event_type == "chess_board"
    assert event.payload["last_move"] == "e2e4"
    assert event.payload["san"] == "e4"


@pytest.mark.asyncio
async def test_runners_support_thinking_parameter():
    metadata_list = registry.get_metadata()
    for meta in metadata_list:
        runner = registry.get_runner(meta.id)
        assert runner is not None
        sig = inspect.signature(runner.run_stream)
        assert "thinking" in sig.parameters
        assert sig.parameters["thinking"].default == "off"


class _MockToolCallItem:
    def __init__(
        self,
        tool_name: str,
        tool_input: Any,
        output: Any = None,
        deltas: list[str] | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.input = tool_input
        self.output = output
        self.deltas = deltas or ["chunk1"]
        self.drained = False

    def __iter__(self):
        self.drained = True
        return iter(self.deltas)


class _MockMessageItem:
    def __init__(
        self,
        text: list[str] | None = None,
        reasoning: list[str] | None = None,
    ) -> None:
        self.text = text or []
        self.reasoning = reasoning or []


class _MockStream:
    def __init__(self, events: list[tuple[str, Any]]) -> None:
        self.events = events

    def interleave(self, *kinds: str):
        assert "messages" in kinds and "tool_calls" in kinds
        return self.events


class _MockAgent:
    def __init__(self, events: list[tuple[str, Any]]) -> None:
        self.events = events
        self.last_config = None

    def stream_events(self, state: dict[str, Any], version: str, *args, **kwargs):
        assert version == "v3"
        self.last_config = kwargs.get("config")
        return _MockStream(self.events)


@pytest.mark.asyncio
async def test_langgraph_v3_streaming_runners(monkeypatch):
    """Verify that all LangChain runners execute stream_events v3 protocol without regression."""
    # 1. DynamicDelegationRunner
    dd_runner = DynamicDelegationRunner()
    tool_item = _MockToolCallItem(
        tool_name="task",
        tool_input={"subagent_type": "weather", "description": "Check Berlin weather"},
        output="Sunny, 22C",
    )
    dd_events = [
        ("messages", _MockMessageItem(reasoning=["Analyzing request..."])),
        ("tool_calls", tool_item),
        ("messages", _MockMessageItem(text=["The weather in Berlin is sunny."])),
    ]
    monkeypatch.setattr(dd_runner, "_build_agent", lambda thinking: _MockAgent(dd_events))

    collected = [ev async for ev in dd_runner.run_stream("Weather in Berlin", "sess_dd", thinking="low")]
    types = [e.event_type for e in collected]
    assert types == ["stage", "thought", "subagent", "tool_call", "token", "metrics", "done"]
    assert tool_item.drained is True

    subagent_ev = next(e for e in collected if e.event_type == "subagent")
    assert subagent_ev.payload["name"] == "weather"
    assert subagent_ev.payload["task"] == "Check Berlin weather"

    # Edge case: non-dict tool_input (must not raise 'str' object has no attribute 'get')
    raw_tool_item = _MockToolCallItem(tool_name="raw_tool", tool_input="plain-string-input")
    monkeypatch.setattr(
        dd_runner, "_build_agent", lambda thinking: _MockAgent([("tool_calls", raw_tool_item)])
    )
    edge_events = [ev async for ev in dd_runner.run_stream("Test", "sess_edge")]
    assert any(e.event_type == "tool_call" for e in edge_events)

    # 2. DeepAgentFilesystemRunner
    store = SessionStore()
    fs_runner = DeepAgentFilesystemRunner(session_store=store)
    fs_tool_item = _MockToolCallItem(
        tool_name="task",
        tool_input={"subagent_type": "research-agent", "description": "Research python"},
    )
    write_tool_item = _MockToolCallItem(
        tool_name="write_file",
        tool_input={"file_path": "report.md", "content": "Analysis complete"},
    )
    fs_events = [
        ("messages", _MockMessageItem(reasoning=["Thinking step..."])),
        ("tool_calls", fs_tool_item),
        ("tool_calls", write_tool_item),
        ("messages", _MockMessageItem(text=["Saved report."])),
    ]
    monkeypatch.setattr(fs_runner, "_build_agent", lambda thinking: _MockAgent(fs_events))

    fs_collected = [ev async for ev in fs_runner.run_stream("Research python", "sess_fs", thinking="high")]
    fs_types = [e.event_type for e in fs_collected]
    assert "subagent" in fs_types
    assert "tool_call" in fs_types
    assert "done" in fs_types
    assert store.get("sess_fs")["files"]["report.md"] == "Analysis complete"

    # 3. LangChainSubagentToolRunner
    lc_runner = LangChainSubagentToolRunner()
    lc_tool_item = _MockToolCallItem(
        tool_name="query_weather",
        tool_input={"city": "Tokyo"},
        output="Rainy, 18C",
    )
    lc_events = [
        ("tool_calls", lc_tool_item),
        ("messages", _MockMessageItem(text=["Tokyo weather is rainy."])),
    ]
    monkeypatch.setattr(lc_runner, "_build_agent", lambda thinking: _MockAgent(lc_events))

    lc_collected = [ev async for ev in lc_runner.run_stream("Weather Tokyo", "sess_lc")]
    lc_types = [e.event_type for e in lc_collected]
    assert "subagent" in lc_types
    assert "tool_call" in lc_types
    assert "done" in lc_types
    lc_subagent_ev = next(e for e in lc_collected if e.event_type == "subagent")
    assert lc_subagent_ev.payload["name"] == "weather_specialist"


@pytest.mark.asyncio
async def test_ms_agent_as_tool_runner_streaming(monkeypatch):
    """Verify that MSAgentToolRunner properly captures function_call and function_result."""
    runner = MSAgentToolRunner()

    class _MockSupervisor:
        async def run(self, prompt: str, stream: bool = True):
            yield AgentResponseUpdate(
                contents=[
                    Content.from_text("Analyzing weather request..."),
                    Content(
                        type="function_call",
                        call_id="call_test_1",
                        name="query_weather",
                        arguments='{"city": "Paris"}',
                    ),
                ],
                role="assistant",
            )
            yield AgentResponseUpdate(
                contents=[
                    Content(
                        type="function_result",
                        call_id="call_test_1",
                        name="query_weather",
                        result="Paris weather is cloudy, 16C",
                    ),
                ],
                role="assistant",
            )
            yield AgentResponseUpdate(
                contents=[Content.from_text("The weather in Paris is cloudy.")],
                role="assistant",
            )
            # Redundant done chunk with merge_mode="replace" (must be ignored to prevent duplication)
            yield AgentResponseUpdate(
                contents=[Content(type="text", text="The weather in Paris is cloudy.", merge_mode="replace")],
                role="assistant",
            )

    monkeypatch.setattr(
        "src.core.patterns.ms_agent_as_tool.runner.create_supervisor_agent",
        lambda client, subagent, default_options=None: _MockSupervisor(),
    )

    events = [ev async for ev in runner.run_stream("Paris weather", "sess_ms_test")]
    types = [e.event_type for e in events]
    assert "stage" in types
    assert "subagent" in types
    assert "tool_call" in types
    assert "token" in types
    assert "metrics" in types
    assert "done" in types

    tokens = [e for e in events if e.event_type == "token"]
    assert len(tokens) == 2  # Exactly 2 tokens, replace chunk was ignored without text duplication
    assert tokens[0].payload["delta"] == "Analyzing weather request..."
    assert tokens[1].payload["delta"] == "The weather in Paris is cloudy."

    subagent_ev = next(e for e in events if e.event_type == "subagent")
    assert subagent_ev.payload["name"] == "weather_specialist"
    assert "Paris" in subagent_ev.payload["task"]

    tool_ev = next(e for e in events if e.event_type == "tool_call")
    assert tool_ev.payload["tool"] == "query_weather"
    assert tool_ev.payload["input"] == {"city": "Paris"}
    assert "cloudy" in tool_ev.payload["output"]


@pytest.mark.asyncio
async def test_deepagent_fs_checkpointer_integration(monkeypatch):
    """Verify that DeepAgentFilesystemRunner integrates InMemorySaver and passes thread_id config."""
    store = SessionStore()
    runner = DeepAgentFilesystemRunner(session_store=store)
    assert runner.checkpointer is not None

    mock_agent = _MockAgent([("messages", _MockMessageItem(text=["Turn response"]))])
    monkeypatch.setattr(runner, "_build_agent", lambda thinking: mock_agent)

    events = [ev async for ev in runner.run_stream("What is the state?", "session_multi_turn_abc")]
    assert any(e.event_type == "done" for e in events)

    # Verify that thread_id was passed in config to stream_events
    assert mock_agent.last_config == {"configurable": {"thread_id": "session_multi_turn_abc"}}


@pytest.mark.asyncio
async def test_ms_round_robin_speaker_attribution(monkeypatch):
    """Verify that MSRoundRobinRunner attributes tokens and stages to Writer and Reviewer."""
    runner = MSRoundRobinRunner()

    class _MockWorkflowEvent:
        def __init__(self, ev_type: str, data: Any = None):
            self.type = ev_type
            self.data = data

    class _MockWorkflow:
        async def run(self, prompt: str, stream: bool = True):
            # 1. Writer starts
            yield _MockWorkflowEvent(
                ev_type="group_chat",
                data=type("GroupChatEvent", (), {"participant_name": "Writer"})(),
            )
            yield _MockWorkflowEvent(
                ev_type="intermediate",
                data=AgentResponseUpdate(
                    contents=[Content(type="text", text="Drafting content...", merge_mode="append")],
                    author_name="Writer",
                    role="assistant",
                ),
            )
            # Redundant done chunk with merge_mode="replace" (should be ignored)
            yield _MockWorkflowEvent(
                ev_type="intermediate",
                data=AgentResponseUpdate(
                    contents=[Content(type="text", text="Drafting content...", merge_mode="replace")],
                    author_name="Writer",
                    role="assistant",
                ),
            )
            # 2. Reviewer starts
            yield _MockWorkflowEvent(
                ev_type="group_chat",
                data=type("GroupChatEvent", (), {"participant_name": "Reviewer"})(),
            )
            yield _MockWorkflowEvent(
                ev_type="intermediate",
                data=AgentResponseUpdate(
                    contents=[Content(type="text", text="APPROVE", merge_mode="append")],
                    author_name="Reviewer",
                    role="assistant",
                ),
            )

    monkeypatch.setattr(
        "src.core.patterns.ms_round_robin.runner.build_writer_reviewer_chat",
        lambda participants, max_rounds=6: _MockWorkflow(),
    )

    events = [ev async for ev in runner.run_stream("Draft a note", "sess_rr_test")]
    stages = [e.payload["agent"] for e in events if e.event_type == "stage"]
    assert "Writer" in stages
    assert "Reviewer" in stages

    tokens = [e for e in events if e.event_type == "token"]
    assert len(tokens) == 2  # Exactly 2 tokens, replace chunk was ignored
    assert tokens[0].payload["source"] == "Writer"
    assert tokens[0].payload["delta"] == "Drafting content..."
    assert tokens[1].payload["source"] == "Reviewer"
    assert tokens[1].payload["delta"] == "APPROVE"


def test_code_payload_serialization():
    payload = CodePayload(delta="print('hello')", source="ast_code_agent")
    event = AgentStreamEvent(event_type="code", payload=payload.model_dump())
    assert event.event_type == "code"
    assert event.payload["delta"] == "print('hello')"
    assert event.payload["source"] == "ast_code_agent"


@pytest.mark.asyncio
async def test_ast_code_runner_streaming_and_final_answer(monkeypatch):
    runner = ASTCodeRunner()

    class _MockChunk:
        def __init__(self, content: str, reasoning: str | None = None):
            self.content = content
            self.reasoning = reasoning

    class _MockChatOllama:
        def __init__(self, *args, **kwargs):
            pass

        async def astream(self, messages):
            yield _MockChunk("", reasoning="Analyzing problem...")
            yield _MockChunk("```python\n")
            yield _MockChunk("weather = get_weather('Berlin')\n")
            yield _MockChunk("final_answer({'Berlin': weather})\n")
            yield _MockChunk("```")

    monkeypatch.setattr("src.core.patterns.ast_code_agent.runner.ChatOllama", _MockChatOllama)

    events = [ev async for ev in runner.run_stream("Check Berlin weather", "sess_ast_test", thinking="low")]
    types = [e.event_type for e in events]

    assert "stage" in types
    assert "thought" in types
    assert "code" in types
    assert "tool_call" in types
    assert "token" in types
    assert "done" in types

    # Verify code events contain code deltas
    code_deltas = "".join(e.payload["delta"] for e in events if e.event_type == "code")
    assert "get_weather('Berlin')" in code_deltas

    # Verify tool calls include get_weather and ast_sandbox
    tool_events = [e for e in events if e.event_type == "tool_call"]
    assert any(t.payload["tool"] == "get_weather" for t in tool_events)
    assert any(t.payload["tool"] == "ast_sandbox" for t in tool_events)

    # Verify that the synthesized final answer was emitted as token events
    token_events = [e for e in events if e.event_type == "token"]
    assert len(token_events) > 0
    final_token_text = "".join(t.payload["delta"] for t in token_events)
    assert "Berlin" in final_token_text
    assert "sunny" in final_token_text
    assert "22°C" in final_token_text
    assert "\\u00b0" not in final_token_text

    # Verify done event contains the same answer
    done_ev = next(e for e in events if e.event_type == "done")
    assert "Berlin" in done_ev.payload["final_answer"]


def test_task_tools_strip_reasoning_blocks_to_clean_text():
    from langchain_core.messages import AIMessage, ToolMessage

    from src.core.patterns.dynamic_delegation.task_tool import create_task_tool
    from src.core.patterns.langchain_subagent_tool.tools import create_subagent_tool
    from src.core.patterns.virtual_filesystem.task_tool import create_research_task_tool

    class _MockSubAgent:
        def invoke(self, state):
            return {
                "messages": [
                    AIMessage(
                        content=[
                            {"type": "reasoning", "reasoning": "Internal thoughts...", "index": 0},
                            {"type": "text", "text": "Clean factual answer", "index": 1},
                        ]
                    )
                ],
                "files": {"report.md": "Content"},
            }

    mock_agent = _MockSubAgent()

    # 1. Dynamic delegation task tool
    task_dyn = create_task_tool({"weather": mock_agent})
    cmd_dyn = task_dyn.func(
        description="Test",
        subagent_type="weather",
        state={"messages": []},
        tool_call_id="call_123",
    )
    tool_msg_dyn = cmd_dyn.update["messages"][0]
    assert isinstance(tool_msg_dyn, ToolMessage)
    assert tool_msg_dyn.content == "Clean factual answer"
    assert isinstance(tool_msg_dyn.content, str)

    # 2. Virtual filesystem research task tool
    task_vfs = create_research_task_tool({"research": mock_agent})
    cmd_vfs = task_vfs.func(
        description="Test",
        subagent_type="research",
        state={"messages": [], "files": {}},
        tool_call_id="call_456",
    )
    tool_msg_vfs = cmd_vfs.update["messages"][0]
    assert isinstance(tool_msg_vfs, ToolMessage)
    assert tool_msg_vfs.content == "Clean factual answer"
    assert isinstance(tool_msg_vfs.content, str)
    assert cmd_vfs.update["files"] == {"report.md": "Content"}

    # 3. LangChain subagent tool
    query_tool = create_subagent_tool(mock_agent)
    res_str = query_tool.invoke({"city": "Berlin"})
    assert res_str == "Clean factual answer"


@pytest.mark.asyncio
async def test_dynamic_delegation_runner_streams_reasoning_projection():
    from langchain_core.language_models.chat_model_stream import SyncTextProjection

    class _MockItem:
        def __init__(self):
            self.reasoning = SyncTextProjection()
            self.reasoning.push("Planning")
            self.reasoning.push(" step")
            self.reasoning.complete("Planning step")

            self.text = SyncTextProjection()
            self.text.push("Final")
            self.text.push(" text")
            self.text.complete("Final text")

    class _MockStream:
        def interleave(self, *args):
            yield "messages", _MockItem()

    class _MockAgent:
        def stream_events(self, *args, **kwargs):
            return _MockStream()

    runner = DynamicDelegationRunner()
    runner._build_agent = lambda thinking="off": _MockAgent()

    events = [ev async for ev in runner.run_stream("hello", "sess_1", thinking="low")]
    thought_events = [e for e in events if e.event_type == "thought"]
    token_events = [e for e in events if e.event_type == "token"]

    assert len(thought_events) == 2
    assert "".join(e.payload["delta"] for e in thought_events) == "Planning step"
    assert len(token_events) == 2
    assert "".join(e.payload["delta"] for e in token_events) == "Final text"


@pytest.mark.asyncio
async def test_langgraph_round_robin_debate_streaming(monkeypatch):
    runner = LangGraphRoundRobinDebateRunner()

    class _MockMessage:
        def __init__(self, node: str, text: list[str], reasoning: list[str] | None = None):
            self.node = node
            self.text = text
            self.reasoning = reasoning or []

    class _MockStreamResult:
        def __init__(self, messages):
            self.messages = messages

    class _MockGraph:
        def stream_events(self, state, version, config=None):
            assert version == "v3"
            return _MockStreamResult(
                [
                    _MockMessage("farmer", ["Land ", "matters."], reasoning=["Farmer thinks..."]),
                    _MockMessage("developer", ["Tech ", "is life."], reasoning=["Dev thinks..."]),
                ]
            )

    monkeypatch.setattr(runner, "_build_graph", lambda thinking="off": _MockGraph())

    events = [ev async for ev in runner.run_stream("Life meaning", "sess_rr", thinking="high")]
    types = [e.event_type for e in events]
    assert "stage" in types
    assert "thought" in types
    assert "token" in types
    assert "done" in types
    assert "metrics" in types

    stages = [e.payload["agent"] for e in events if e.event_type == "stage"]
    assert "coordinator" in stages
    assert "Farmer" in stages
    assert "Developer" in stages

    thoughts = [e.payload for e in events if e.event_type == "thought"]
    assert any(t["source"] == "Farmer" and "Farmer thinks" in t["delta"] for t in thoughts)
    assert any(t["source"] == "Developer" and "Dev thinks" in t["delta"] for t in thoughts)

    tokens = [e.payload for e in events if e.event_type == "token"]
    assert any(t["source"] == "Farmer" and "Land " in t["delta"] for t in tokens)
    assert any(t["source"] == "Developer" and "Tech " in t["delta"] for t in tokens)


@pytest.mark.asyncio
async def test_langgraph_moderated_debate_streaming(monkeypatch):
    runner = LangGraphModeratedDebateRunner()

    class _MockMessage:
        def __init__(self, node: str, text: list[str], reasoning: list[str] | None = None):
            self.node = node
            self.text = text
            self.reasoning = reasoning or []

    class _MockStreamResult:
        def __init__(self, messages):
            self.messages = messages

    class _MockGraph:
        def stream_events(self, state, version, config=None):
            assert version == "v3"
            return _MockStreamResult(
                [
                    _MockMessage(
                        "moderator", ["Welcome to the debate."], reasoning=["Moderator planning..."]
                    ),
                    _MockMessage("activist", ["We must act."], reasoning=["Activist passion..."]),
                    _MockMessage("moderator", ["Concluding synthesis."], reasoning=["Synthesizing..."]),
                ]
            )

    monkeypatch.setattr(runner, "_build_graph", lambda thinking="off": _MockGraph())

    events = [ev async for ev in runner.run_stream("Climate ethics", "sess_mod", thinking="high")]
    types = [e.event_type for e in events]
    assert "stage" in types
    assert "thought" in types
    assert "token" in types
    assert "done" in types
    assert "metrics" in types

    stages = [e.payload["agent"] for e in events if e.event_type == "stage"]
    assert "moderator" in stages
    assert "Moderator" in stages
    assert "Activist" in stages

    thoughts = [e.payload for e in events if e.event_type == "thought"]
    assert any(t["source"] == "Moderator" and "Moderator planning" in t["delta"] for t in thoughts)
    assert any(t["source"] == "Activist" and "Activist passion" in t["delta"] for t in thoughts)


def test_langgraph_moderator_node_suppresses_callbacks():
    """Verify ModeratorDecision structured model call suppresses callbacks to avoid leaking JSON into stream."""
    from langchain_core.messages import HumanMessage

    from src.core.patterns.langgraph_moderated_debate.personas import create_moderator_node
    from src.core.patterns.langgraph_moderated_debate.state import ModeratorDecision

    recorded_configs = []

    class _MockStructuredModel:
        def invoke(self, prompt, config=None):
            recorded_configs.append(config)
            return ModeratorDecision(
                thought="Internal routing rationale",
                next_speaker="activist",
                question_or_context="Opening question for panel",
            )

    class _MockModel:
        def with_structured_output(self, schema):
            return _MockStructuredModel()

    node_func = create_moderator_node(_MockModel())
    state = {
        "messages": [HumanMessage(content="Test topic")],
        "current_round": 0,
        "max_rounds": 6,
        "next_speaker": "moderator",
    }
    result = node_func(state)

    # 1. Callbacks must be explicitly suppressed
    assert len(recorded_configs) == 1
    assert recorded_configs[0] == {"callbacks": []}

    # 2. Next speaker routed correctly
    assert result["next_speaker"] == "activist"

    # 3. Spoken transition message does not leak internal thought JSON
    assert len(result["messages"]) == 1
    spoken_text = result["messages"][0].content
    assert "Thank you. Next, let us hear from our Activist: Opening question for panel" in spoken_text
    assert "Internal routing rationale" not in spoken_text
    assert "{" not in spoken_text
