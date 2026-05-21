import hashlib
import hmac
from pathlib import Path
from bridge.hmac_auth import verify_hmac


def _make_signature(event_id, breakout_id, project_id, timestamp, file_bytes, secret):
    file_sha256 = hashlib.sha256(file_bytes).hexdigest()
    canonical = f"{event_id}\n{breakout_id}\n{project_id}\n{timestamp}\n{file_sha256}"
    return hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def test_verify_hmac_valid(tmp_path):
    file_bytes = b"fake audio content"
    file_path = tmp_path / "rec.webm"
    file_path.write_bytes(file_bytes)

    sig = _make_signature("ev-1", "br-1", "proj-abc", "2026-04-19T10:00:00Z", file_bytes, "secret")
    assert verify_hmac("ev-1", "br-1", "proj-abc", "2026-04-19T10:00:00Z", file_path, sig, "secret") is True


def test_verify_hmac_wrong_signature(tmp_path):
    file_path = tmp_path / "rec.webm"
    file_path.write_bytes(b"content")
    assert verify_hmac("ev-1", "br-1", "proj-abc", "2026-04-19T10:00:00Z", file_path, "badsig", "secret") is False


def test_verify_hmac_tampered_metadata(tmp_path):
    file_bytes = b"content"
    file_path = tmp_path / "rec.webm"
    file_path.write_bytes(file_bytes)

    sig = _make_signature("ev-1", "br-1", "proj-abc", "2026-04-19T10:00:00Z", file_bytes, "secret")
    # tamper with event_id
    assert verify_hmac("ev-TAMPERED", "br-1", "proj-abc", "2026-04-19T10:00:00Z", file_path, sig, "secret") is False


def test_verify_hmac_wrong_secret(tmp_path):
    file_bytes = b"content"
    file_path = tmp_path / "rec.webm"
    file_path.write_bytes(file_bytes)

    sig = _make_signature("ev-1", "br-1", "proj-abc", "2026-04-19T10:00:00Z", file_bytes, "secret")
    assert verify_hmac("ev-1", "br-1", "proj-abc", "2026-04-19T10:00:00Z", file_path, sig, "wrong-secret") is False


def test_verify_hmac_tampered_project_id(tmp_path):
    file_bytes = b"content"
    file_path = tmp_path / "rec.webm"
    file_path.write_bytes(file_bytes)

    sig = _make_signature("ev-1", "br-1", "proj-abc", "2026-04-19T10:00:00Z", file_bytes, "secret")
    # tamper with project_id — HMAC must reject
    assert verify_hmac("ev-1", "br-1", "proj-TAMPERED", "2026-04-19T10:00:00Z", file_path, sig, "secret") is False
