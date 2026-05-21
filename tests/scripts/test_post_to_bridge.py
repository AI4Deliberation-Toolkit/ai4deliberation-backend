import tempfile
from pathlib import Path

from bridge.hmac_auth import verify_hmac
from scripts.post_to_bridge import compute_signature


def _write_temp_file(content: bytes) -> Path:
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


def test_signature_verifies_against_bridge():
    secret = "test-secret-xyz"
    file_path = _write_temp_file(b"hello world content")
    try:
        sig = compute_signature(
            event_id="ev-1",
            breakout_id="room-a",
            project_id="proj-abc",
            timestamp="2026-05-11T10:00:00Z",
            file_path=file_path,
            secret=secret,
        )
        assert verify_hmac(
            event_id="ev-1",
            breakout_id="room-a",
            project_id="proj-abc",
            timestamp="2026-05-11T10:00:00Z",
            file_path=file_path,
            signature=sig,
            secret=secret,
        )
    finally:
        file_path.unlink()


def test_signature_changes_when_file_changes():
    secret = "test-secret-xyz"
    p1 = _write_temp_file(b"content one")
    p2 = _write_temp_file(b"content two")
    try:
        s1 = compute_signature("ev-1", "room-a", "proj-abc", "2026-05-11T10:00:00Z", p1, secret)
        s2 = compute_signature("ev-1", "room-a", "proj-abc", "2026-05-11T10:00:00Z", p2, secret)
        assert s1 != s2
    finally:
        p1.unlink()
        p2.unlink()


def test_signature_changes_when_secret_changes():
    file_path = _write_temp_file(b"same content")
    try:
        s1 = compute_signature("ev-1", "room-a", "proj-abc", "2026-05-11T10:00:00Z", file_path, "secret-a")
        s2 = compute_signature("ev-1", "room-a", "proj-abc", "2026-05-11T10:00:00Z", file_path, "secret-b")
        assert s1 != s2
    finally:
        file_path.unlink()
