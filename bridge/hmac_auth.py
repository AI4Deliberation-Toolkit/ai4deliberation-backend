import hashlib
import hmac
from pathlib import Path


def _compute_file_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def verify_hmac(
    event_id: str,
    breakout_id: str,
    timestamp: str,
    file_path: Path,
    signature: str,
    secret: str,
) -> bool:
    file_sha256 = _compute_file_sha256(file_path)
    canonical = f"{event_id}\n{breakout_id}\n{timestamp}\n{file_sha256}"
    expected = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
