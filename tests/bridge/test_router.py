import hashlib
import hmac
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bridge.router import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_form(file_bytes=b"fake audio", event_id="ev-1", breakout_id="br-1",
               project_id="proj-abc", timestamp="2026-04-19T10:00:00Z", secret="test-secret"):
    sha = hashlib.sha256(file_bytes).hexdigest()
    canonical = f"{event_id}\n{breakout_id}\n{project_id}\n{timestamp}\n{sha}"
    sig = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return {
        "data": {"event_id": event_id, "breakout_id": breakout_id,
                 "project_id": project_id, "timestamp": timestamp, "hmac_signature": sig},
        "files": {"file": ("rec.webm", file_bytes, "audio/webm")},
    }


@patch("bridge.router.HMAC_SECRET", "test-secret")
@patch("bridge.router.process_recording", new_callable=AsyncMock)
def test_valid_request_returns_202(mock_pipeline):
    form = _make_form()
    response = client.post("/recordings/incoming", data=form["data"], files=form["files"])
    assert response.status_code == 202


@patch("bridge.router.HMAC_SECRET", "test-secret")
def test_invalid_hmac_returns_400():
    form = _make_form()
    tampered = dict(form["data"])
    sig = tampered["hmac_signature"]
    tampered["hmac_signature"] = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    response = client.post(
        "/recordings/incoming",
        data=tampered,
        files=form["files"],
    )
    assert response.status_code == 400


@patch("bridge.router.HMAC_SECRET", "test-secret")
@patch("bridge.router.process_recording", new_callable=AsyncMock)
def test_background_task_is_dispatched(mock_pipeline):
    form = _make_form()
    client.post("/recordings/incoming", data=form["data"], files=form["files"])
    mock_pipeline.assert_called_once()
    args = mock_pipeline.call_args[0]
    assert isinstance(args[0], Path)   # file_path
    assert args[1] == "ev-1"           # event_id
    assert args[2] == "br-1"           # breakout_id
    assert args[3] == "proj-abc"       # project_id
    assert args[4] == "2026-04-19T10:00:00Z"  # timestamp
