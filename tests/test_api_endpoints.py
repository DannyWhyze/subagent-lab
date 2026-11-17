"""API endpoints integration tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from src.core.models import AgentStreamEvent, StreamRequest, ThoughtPayload
from src.main import app


@pytest.mark.asyncio
async def test_api_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["patterns_count"] >= 4


@pytest.mark.asyncio
async def test_list_patterns():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/patterns")
        assert resp.status_code == 200
        patterns = resp.json()
        ids = [p["id"] for p in patterns]
        assert "dynamic_delegation" in ids
        assert "virtual_filesystem" in ids
        assert "langchain_subagent_tool" in ids
        assert "ms_agent_as_tool" in ids
        assert "ms_round_robin" in ids
        assert "ms_round_robin_debate" in ids
        assert "ms_moderated_debate" in ids
        assert "ms_chess" in ids
        assert "ast_code_agent" in ids
        assert "smolagents_managed" in ids
        assert "mock_runner" in ids

        for p in patterns:
            assert "example_prompts" in p
            assert isinstance(p["example_prompts"], list)
            assert len(p["example_prompts"]) >= 1


@pytest.mark.asyncio
async def test_stream_nonexistent_pattern_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/stream",
            json={
                "pattern_id": "nonexistent_pattern",
                "session_id": "test_sess",
                "prompt": "Hello",
            },
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stream_validation_error_422():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid pattern_id with special characters
        resp = await client.post(
            "/api/stream",
            json={
                "pattern_id": "../invalid/path",
                "session_id": "test_sess",
                "prompt": "Hello",
            },
        )
        assert resp.status_code == 422


def test_stream_request_thinking_validation():
    req = StreamRequest(pattern_id="mock_runner", session_id="s1", prompt="test", thinking="low")
    assert req.thinking == "low"

    # Default thinking should be "off"
    default_req = StreamRequest(pattern_id="mock_runner", session_id="s1", prompt="test")
    assert default_req.thinking == "off"

    # Invalid thinking mode should fail validation
    with pytest.raises(ValidationError):
        StreamRequest(pattern_id="mock_runner", session_id="s1", prompt="test", thinking="ultra")


def test_thought_payload_serialization():
    payload = ThoughtPayload(delta="Reflecting on the solution...", source="supervisor")
    event = AgentStreamEvent(event_type="thought", payload=payload.model_dump())
    assert event.event_type == "thought"
    assert event.payload["delta"] == "Reflecting on the solution..."
    assert event.payload["source"] == "supervisor"


@pytest.mark.asyncio
async def test_chess_move_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. State for fresh session returns 200 with initial board and opening moves
        resp = await client.get("/api/chess/state?session_id=fresh_chess_session")
        assert resp.status_code == 200
        fresh_data = resp.json()
        assert fresh_data["turn"] == 1
        assert fresh_data["current_player"] == "White"
        assert len(fresh_data["legal_moves"]) == 20

        # Invalid session format returns 400
        invalid_resp = await client.get("/api/chess/state?session_id=invalid$$$session")
        assert invalid_resp.status_code == 400

        # 2. Make valid human move
        resp = await client.post(
            "/api/chess/move",
            json={"session_id": "test_chess_session_1", "move": "e4"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["san"] == "e4"
        assert data["last_move"] == "e2e4"
        assert "fen" in data
        assert data["game_over"] is False

        # 3. State endpoint now returns 200 with board info
        state_resp = await client.get("/api/chess/state?session_id=test_chess_session_1")
        assert state_resp.status_code == 200
        state_data = state_resp.json()
        assert state_data["current_player"] == "Black"
        assert len(state_data["legal_moves"]) > 0

        # 4. Illegal move returns 400
        bad_move_resp = await client.post(
            "/api/chess/move",
            json={"session_id": "test_chess_session_1", "move": "e4"},
        )
        assert bad_move_resp.status_code == 400
        assert "Illegal move" in bad_move_resp.json()["detail"]


@pytest.mark.asyncio
async def test_favicon_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/favicon.ico")
        assert resp.status_code == 204
