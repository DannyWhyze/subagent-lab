"""SSE streaming and disconnect cancellation tests."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.sse_handler import sse_event_generator
from src.core.models import StreamRequest
from src.core.registry import MockAgentRunner
from src.main import app


@pytest.mark.asyncio
async def test_sse_stream_full_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        req_payload = {
            "pattern_id": "mock_runner",
            "session_id": "test_session_sse",
            "prompt": "Test query for SSE stream",
        }
        async with client.stream("POST", "/api/stream", json=req_payload) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            events = []
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    event_data = json.loads(line[6:])
                    events.append(event_data)

            event_types = [e["event_type"] for e in events]
            assert "stage" in event_types
            assert "subagent" in event_types
            assert "tool_call" in event_types
            assert "token" in event_types
            assert "metrics" in event_types
            assert "done" in event_types


class FakeDisconnectRequest:
    """Fake Request simulating client disconnect after initial yield."""

    def __init__(self, disconnect_after: int = 1) -> None:
        self.count = 0
        self.disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self.count += 1
        return self.count > self.disconnect_after


@pytest.mark.asyncio
async def test_sse_disconnect_cancellation():
    fake_req = FakeDisconnectRequest(disconnect_after=1)
    runner = MockAgentRunner(delay_ms=20.0)
    req_data = StreamRequest(
        pattern_id="mock_runner",
        session_id="disconnect_sess",
        prompt="Disconnect test",
    )

    collected_events = []
    async for raw_line in sse_event_generator(runner, fake_req, req_data):  # type: ignore
        collected_events.append(raw_line)

    # Stream should stop early due to disconnect
    assert len(collected_events) < 10


@pytest.mark.asyncio
async def test_sse_stream_with_thinking_mode():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        req_payload = {
            "pattern_id": "mock_runner",
            "session_id": "test_session_thinking",
            "prompt": "Test thinking stream",
            "thinking": "high",
        }
        async with client.stream("POST", "/api/stream", json=req_payload) as response:
            assert response.status_code == 200
            events = []
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            event_types = [e["event_type"] for e in events]
            assert "thought" in event_types
            thought_events = [e for e in events if e["event_type"] == "thought"]
            assert len(thought_events) > 0
            assert thought_events[0]["payload"]["source"] == "mock_supervisor"
