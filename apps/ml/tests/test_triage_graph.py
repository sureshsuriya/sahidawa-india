from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import pytest

from main import app
import services.triage_graph as triage_graph

client = TestClient(app)


@patch("routers.triage.run_triage_flow", new_callable=AsyncMock)
def test_triage_chat_endpoint_success(mock_run_triage):
    mock_run_triage.return_value = {
        "response": "How long have you had this pain?",
        "emergency": False,
        "language": "English",
        "summary": "Mild headache symptoms",
        "recommendations": ["Rest", "Hydrate"],
        "disclaimer": "Informational only",
        "details": {"onset": "unknown", "severity": "mild"},
    }

    payload = {
        "messages": [{"role": "user", "content": "I have a headache."}],
        "locale": "en",
    }

    response = client.post("/triage/chat", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "How long have you had this pain?"
    assert data["emergency"] is False
    assert data["language"] == "English"
    assert "onset" in data["details"]
    mock_run_triage.assert_awaited_once()


# Helpers

class _FakeRedis:
    def __init__(self):
        self.store: dict = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        return True

    async def delete(self, *keys):
        return sum(1 for k in keys if self.store.pop(k, None) is not None)


# init_checkpointer tests

def test_init_checkpointer_stays_manual_when_package_unavailable(monkeypatch):
    """Package missing → CHECKPOINTER_MODE must stay 'manual'."""
    monkeypatch.setattr(triage_graph, "CHECKPOINTER_MODE", "manual")
    monkeypatch.setattr(triage_graph, "REDIS_CHECKPOINTER_AVAILABLE", False)

    asyncio.run(triage_graph.init_checkpointer())

    assert triage_graph.CHECKPOINTER_MODE == "manual"


def test_init_checkpointer_stays_manual_on_asetup_failure(monkeypatch):
    """asetup() raises (e.g. no RedisJSON) → must not propagate, mode stays 'manual'."""
    monkeypatch.setattr(triage_graph, "CHECKPOINTER_MODE", "manual")
    monkeypatch.setattr(triage_graph, "REDIS_CHECKPOINTER_AVAILABLE", True)
    monkeypatch.setattr(triage_graph, "LANGGRAPH_AVAILABLE", True)
    monkeypatch.setattr(triage_graph, "_native_triage_app", None)
    monkeypatch.setattr(triage_graph, "_checkpointer_stack", None)

    mock_saver = AsyncMock()
    mock_saver.asetup = AsyncMock(side_effect=ConnectionError("No RedisJSON module"))

    class _FakeCM:
        async def __aenter__(self):
            return mock_saver

        async def __aexit__(self, *args):
            return False

    class _FakeAsyncRedisSaver:
        @staticmethod
        def from_conn_string(url):
            return _FakeCM()

    monkeypatch.setattr(triage_graph, "AsyncRedisSaver", _FakeAsyncRedisSaver)

    asyncio.run(triage_graph.init_checkpointer())  # must not raise

    assert triage_graph.CHECKPOINTER_MODE == "manual"
    assert triage_graph._native_triage_app is None

# run_triage_flow — native-mode tests

@pytest.mark.anyio
async def test_run_triage_flow_native_mode_passes_thread_id_in_config(monkeypatch):
    """Native mode must forward session_id as thread_id in the LangGraph config."""
    monkeypatch.setattr(triage_graph, "LANGGRAPH_AVAILABLE", True)
    monkeypatch.setattr(triage_graph, "CHECKPOINTER_MODE", "native")

    captured_config: dict = {}

    async def _fake_ainvoke(state, config=None):
        captured_config.update(config or {})
        return {
            "response": "Noted.",
            "emergency_detected": False,
            "language": "English",
            "final_summary": "",
            "recommendations": [],
            "disclaimer": "",
            "collected_info": {},
            "retrieved_medicines": [],
        }

    fake_native_app = MagicMock()
    fake_native_app.ainvoke = _fake_ainvoke
    monkeypatch.setattr(triage_graph, "_native_triage_app", fake_native_app)
    monkeypatch.setattr(triage_graph, "_save_session_state", AsyncMock())

    result = await triage_graph.run_triage_flow(
        [{"role": "user", "content": "I feel dizzy"}], session_id="thread-abc"
    )

    assert captured_config.get("configurable", {}).get("thread_id") == "thread-abc"
    assert result["response"] == "Noted."


@pytest.mark.anyio
async def test_run_triage_flow_native_mid_run_failure_falls_through(monkeypatch):
    """Native ainvoke raises → falls through to manual triage_app, returns valid response."""
    fake_redis = _FakeRedis()
    monkeypatch.setattr(triage_graph, "redis_client", fake_redis)
    monkeypatch.setattr(triage_graph, "LANGGRAPH_AVAILABLE", True)
    monkeypatch.setattr(triage_graph, "CHECKPOINTER_MODE", "native")

    fake_native_app = MagicMock()
    fake_native_app.ainvoke = AsyncMock(side_effect=ConnectionError("Redis blip"))
    monkeypatch.setattr(triage_graph, "_native_triage_app", fake_native_app)

    fallback_state = {
        "response": "Please describe your symptoms.",
        "emergency_detected": False,
        "language": "English",
        "final_summary": "",
        "recommendations": [],
        "disclaimer": "",
        "collected_info": {},
        "retrieved_medicines": [],
    }
    fake_fallback_app = MagicMock()
    fake_fallback_app.ainvoke = AsyncMock(return_value=fallback_state)
    monkeypatch.setattr(triage_graph, "triage_app", fake_fallback_app)

    result = await triage_graph.run_triage_flow(
        [{"role": "user", "content": "I feel unwell"}], session_id="session-blip"
    )

    fake_native_app.ainvoke.assert_awaited_once()
    fake_fallback_app.ainvoke.assert_awaited_once()
    assert result["response"] == "Please describe your symptoms."


@pytest.mark.anyio
async def test_run_triage_flow_native_mode_shadow_writes_to_manual_keys(monkeypatch):
    """Native mode must shadow-write state to the manual key namespace."""
    fake_redis = _FakeRedis()
    monkeypatch.setattr(triage_graph, "redis_client", fake_redis)
    monkeypatch.setattr(triage_graph, "LANGGRAPH_AVAILABLE", True)
    monkeypatch.setattr(triage_graph, "CHECKPOINTER_MODE", "native")

    native_state = {
        "response": "Tell me more.",
        "emergency_detected": False,
        "language": "Hindi",
        "final_summary": "",
        "recommendations": [],
        "disclaimer": "",
        "collected_info": {"onset": "2 days"},
        "retrieved_medicines": [],
    }
    fake_native_app = MagicMock()
    fake_native_app.ainvoke = AsyncMock(return_value=native_state)
    monkeypatch.setattr(triage_graph, "_native_triage_app", fake_native_app)

    await triage_graph.run_triage_flow(
        [{"role": "user", "content": "Mujhe bukhar hai"}], session_id="session-shadow"
    )

    loaded = await triage_graph._load_session_state("session-shadow")
    assert loaded is not None
    assert loaded["language"] == "Hindi"
    assert loaded["collected_info"]["onset"] == "2 days"
