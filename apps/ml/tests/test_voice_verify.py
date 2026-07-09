import io
import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app
from routers import voice_verify
from utils import audio_upload


client = TestClient(app)


def test_voice_verify_rejects_oversized_audio_before_transcription(monkeypatch):
    monkeypatch.setattr(audio_upload, "MAX_AUDIO_SIZE_BYTES", 10)
    monkeypatch.setattr(
        voice_verify,
        "get_whisper_model",
        lambda: (_ for _ in ()).throw(
            AssertionError("Oversized upload should be rejected before transcription")
        ),
    )

    response = client.post(
        "/voice/verify",
        files={"audio": ("large.webm", io.BytesIO(b"x" * 11), "audio/webm")},
    )

    assert response.status_code == 413
    assert "Audio file too large" in response.json()["detail"]
