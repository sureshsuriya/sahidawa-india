import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
import services.triage_graph as triage_graph

client = TestClient(app)


class FakeRedis:
    """Minimal in-memory stand-in for the async Redis client used in tests."""

    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        return True


# ---------------------------------------------------------------------------
# services.triage_graph — unit-level tests
# ---------------------------------------------------------------------------

def test_save_and_load_session_state_roundtrip(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(triage_graph, "redis_client", fake_redis)

    state = {
        "language": "Hindi",
        "emergency_detected": False,
        "collected_info": {"onset": "2 days ago", "severity": "mild"},
        "retrieved_medicines": [{"brand_name": "Crocin"}],
        "messages": [{"role": "user", "content": "should not be persisted"}],
    }

    asyncio.run(triage_graph._save_session_state("session-abc", state))
    loaded = asyncio.run(triage_graph._load_session_state("session-abc"))

    assert loaded["language"] == "Hindi"
    assert loaded["collected_info"]["onset"] == "2 days ago"
    assert loaded["retrieved_medicines"] == [{"brand_name": "Crocin"}]
    # messages are intentionally excluded from persisted state
    assert "messages" not in loaded


def test_load_session_state_missing_session_returns_none(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(triage_graph, "redis_client", fake_redis)

    assert asyncio.run(triage_graph._load_session_state("does-not-exist")) is None


def test_load_session_state_corrupt_json_returns_none(monkeypatch):
    fake_redis = FakeRedis()
    fake_redis.store[triage_graph._session_key("bad-session")] = "not valid json {"
    monkeypatch.setattr(triage_graph, "redis_client", fake_redis)

    assert asyncio.run(triage_graph._load_session_state("bad-session")) is None


def test_load_session_state_redis_error_returns_none(monkeypatch):
    class BrokenRedis:
        async def get(self, key):
            raise ConnectionError("redis unavailable")

    monkeypatch.setattr(triage_graph, "redis_client", BrokenRedis())

    # Should not raise — gracefully falls back to a fresh session.
    assert asyncio.run(triage_graph._load_session_state("session-x")) is None


def test_run_triage_flow_reuses_persisted_state(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(triage_graph, "redis_client", fake_redis)
    monkeypatch.setattr(triage_graph, "LANGGRAPH_AVAILABLE", True)

    # Pre-populate a session with prior collected_info, as if turn 1 already ran.
    asyncio.run(
        triage_graph._save_session_state(
            "session-continue",
            {
                "language": "English",
                "emergency_detected": False,
                "collected_info": {"onset": "yesterday", "severity": "unknown"},
                "retrieved_medicines": [],
            },
        )
    )

    captured_initial_state = {}

    def fake_invoke(initial_state):
        captured_initial_state.update(initial_state)
        return {
            "response": "Got it, thanks.",
            "emergency_detected": False,
            "language": "English",
            "final_summary": "ok",
            "recommendations": [],
            "disclaimer": "",
            "collected_info": initial_state["collected_info"],
        }

    fake_app = MagicMock()
    fake_app.invoke.side_effect = fake_invoke
    monkeypatch.setattr(triage_graph, "triage_app", fake_app)

    new_messages = [{"role": "user", "content": "it's also severe now"}]
    result = triage_graph.run_triage_flow(new_messages, session_id="session-continue")

    # Prior turn's collected_info should have been rehydrated into the graph's
    # starting state instead of being lost.
    assert captured_initial_state["collected_info"]["onset"] == "yesterday"
    # This request's messages always take precedence over any stored ones.
    assert captured_initial_state["messages"] == new_messages
    assert result["response"] == "Got it, thanks."


def test_run_triage_flow_missing_session_starts_fresh(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(triage_graph, "redis_client", fake_redis)
    monkeypatch.setattr(triage_graph, "LANGGRAPH_AVAILABLE", True)

    captured_initial_state = {}

    def fake_invoke(initial_state):
        captured_initial_state.update(initial_state)
        return {
            "response": "Hello, how can I help?",
            "emergency_detected": False,
            "language": "English",
            "final_summary": "",
            "recommendations": [],
            "disclaimer": "",
            "collected_info": {},
        }

    fake_app = MagicMock()
    fake_app.invoke.side_effect = fake_invoke
    monkeypatch.setattr(triage_graph, "triage_app", fake_app)

    result = triage_graph.run_triage_flow(
        [{"role": "user", "content": "hi"}], session_id="brand-new-or-expired-session"
    )

    # No prior state existed, so it should fall back to defaults, not error out.
    assert captured_initial_state["collected_info"] == {}
    assert result["response"] == "Hello, how can I help?"


# ---------------------------------------------------------------------------
# routers.triage — endpoint-level tests
# ---------------------------------------------------------------------------

@patch("routers.triage.run_triage_flow")
def test_triage_chat_generates_session_id_when_omitted(mock_run_triage):
    mock_run_triage.return_value = {
        "response": "How long have you had this pain?",
        "emergency": False,
        "language": "English",
        "summary": "Mild headache symptoms",
        "recommendations": ["Rest"],
        "disclaimer": "Informational only",
        "details": {"onset": "unknown"},
    }

    payload = {"messages": [{"role": "user", "content": "I have a headache."}]}
    response = client.post("/triage/chat", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data and data["session_id"]

    # The generated session_id should have been forwarded to run_triage_flow.
    _, kwargs = mock_run_triage.call_args
    assert kwargs["session_id"] == data["session_id"]


@patch("routers.triage.run_triage_flow")
def test_triage_chat_reuses_supplied_session_id(mock_run_triage):
    mock_run_triage.return_value = {
        "response": "Thanks, noted.",
        "emergency": False,
        "language": "English",
        "summary": "",
        "recommendations": [],
        "disclaimer": "",
        "details": {},
    }

    payload = {
        "messages": [{"role": "user", "content": "it's worse now"}],
        "session_id": "existing-session-123",
    }
    response = client.post("/triage/chat", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "existing-session-123"

    _, kwargs = mock_run_triage.call_args
    assert kwargs["session_id"] == "existing-session-123"