import os
import tempfile
import time
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
from routers.tts import CACHE_DIR, prune_cache, MAX_CACHE_FILES, MAX_CACHE_SIZE_MB

client = TestClient(app)

def test_tts_health():
    res = client.get("/voice/tts/health")
    assert res.status_code == 200
    assert "status" in res.json()

def test_prune_cache_by_file_count(monkeypatch):
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_cache_dir = Path(temp_dir)
        monkeypatch.setattr("routers.tts.CACHE_DIR", mock_cache_dir)
        monkeypatch.setattr("routers.tts.MAX_CACHE_FILES", 3)
        monkeypatch.setattr("routers.tts.MAX_CACHE_SIZE_MB", 100)
        
        file1 = mock_cache_dir / "test_1.mp3.gz"
        file2 = mock_cache_dir / "test_2.mp3.gz"
        file3 = mock_cache_dir / "test_3.mp3.gz"
        file4 = mock_cache_dir / "test_4.mp3.gz"
        
        file1.write_bytes(b"a" * 10)
        time.sleep(0.01)
        file2.write_bytes(b"b" * 10)
        time.sleep(0.01)
        file3.write_bytes(b"c" * 10)
        time.sleep(0.01)
        file4.write_bytes(b"d" * 10)
        
        prune_cache()
        
        assert not file1.exists()
        assert file2.exists()
        assert file3.exists()
        assert file4.exists()

def test_prune_cache_by_size(monkeypatch):
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_cache_dir = Path(temp_dir)
        monkeypatch.setattr("routers.tts.CACHE_DIR", mock_cache_dir)
        monkeypatch.setattr("routers.tts.MAX_CACHE_FILES", 100)
        monkeypatch.setattr("routers.tts.MAX_CACHE_SIZE_MB", 0.00003)
        
        file1 = mock_cache_dir / "test_size_1.mp3.gz"
        file2 = mock_cache_dir / "test_size_2.mp3.gz"
        file3 = mock_cache_dir / "test_size_3.mp3.gz"
        
        file1.write_bytes(b"a" * 15)
        time.sleep(0.01)
        file2.write_bytes(b"b" * 15)
        time.sleep(0.01)
        file3.write_bytes(b"c" * 10)
        
        prune_cache()
        
        assert not file1.exists()
        assert file2.exists()
        assert file3.exists()


class FakeRedis:
    """Minimal in-memory stand-in for a redis.Redis client, used to test
    the TTS Redis cache helpers without a real Redis server."""

    def __init__(self):
        self.store = {}
        self.ttls = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttls[key] = ttl


def test_redis_cache_roundtrip(monkeypatch):
    from routers.tts import get_cache_key, upload_to_redis_cache, download_from_redis_cache

    fake_redis = FakeRedis()
    monkeypatch.setattr("routers.tts.redis_client", fake_redis)

    cache_key = get_cache_key("Hello world", "en-IN", "FEMALE")

    # Nothing cached yet
    assert download_from_redis_cache(cache_key) is None

    upload_to_redis_cache(cache_key, b"fake-audio-bytes")

    # Repeated request should now be served from Redis
    assert download_from_redis_cache(cache_key) == b"fake-audio-bytes"


def test_redis_cache_sets_24_hour_ttl(monkeypatch):
    from routers.tts import get_cache_key, upload_to_redis_cache, REDIS_CACHE_TTL_SECONDS

    fake_redis = FakeRedis()
    monkeypatch.setattr("routers.tts.redis_client", fake_redis)

    cache_key = get_cache_key("TTL check", "hi-IN", "FEMALE")
    upload_to_redis_cache(cache_key, b"audio-bytes")

    assert fake_redis.ttls[f"tts:{cache_key}"] == REDIS_CACHE_TTL_SECONDS
    assert REDIS_CACHE_TTL_SECONDS == 86400


def test_redis_cache_noop_when_client_missing(monkeypatch):
    from routers.tts import upload_to_redis_cache, download_from_redis_cache

    monkeypatch.setattr("routers.tts.redis_client", None)

    # Should safely no-op instead of raising when Redis isn't configured
    assert download_from_redis_cache("some-key") is None
    upload_to_redis_cache("some-key", b"data")


def test_generate_endpoint_uses_redis_cache_and_skips_cloud_tts(monkeypatch):
    """Proves the acceptance criterion: a Redis cache hit must short-circuit
    the request before any external TTS provider is called, and the audio
    returned to the client is exactly the cached audio."""
    import gzip
    import base64
    from routers import tts as tts_module

    fake_redis = FakeRedis()
    monkeypatch.setattr(tts_module, "redis_client", fake_redis)
    monkeypatch.setattr(tts_module, "supabase_client", None)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Cloud TTS provider should not be called on a Redis cache hit")

    monkeypatch.setattr(tts_module, "generate_with_google", _fail_if_called)
    monkeypatch.setattr(tts_module, "generate_with_azure", _fail_if_called)

    text, language_code, gender = "Hello world", "en-IN", "FEMALE"
    cache_key = tts_module.get_cache_key(text, language_code, gender)
    fake_audio = b"fake-audio-bytes"
    fake_redis.setex(f"tts:{cache_key}", tts_module.REDIS_CACHE_TTL_SECONDS, gzip.compress(fake_audio))

    # Make sure local disk is a miss so the Redis path is exercised, and clean
    # up the temp cache dir automatically afterwards
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setattr(tts_module, "CACHE_DIR", Path(temp_dir))

        res = client.post(
            "/voice/tts/generate",
            json={"text": text, "language_code": language_code, "gender": gender},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["cached"] is True
    assert body["provider"] == "redis-cache"
    assert base64.b64decode(body["audio_base64"]) == fake_audio