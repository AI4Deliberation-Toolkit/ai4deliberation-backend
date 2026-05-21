"""Mimic-Frankly client. Signs and POSTs an MP4 to the bridge endpoint.

Reads BRIDGE_HMAC_SECRET and BRIDGE_URL from environment.
"""

import argparse
import hashlib
import hmac
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx


# Intentionally reimplemented (not imported from bridge.hmac_auth): this script
# mimics an external Frankly client and stays decoupled from the bridge package.
# Compatibility with the bridge is verified by tests/scripts/test_post_to_bridge.py.
def _compute_file_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def compute_signature(
    event_id: str,
    breakout_id: str,
    project_id: str,
    timestamp: str,
    file_path: Path,
    secret: str,
) -> str:
    file_sha256 = _compute_file_sha256(file_path)
    canonical = f"{event_id}\n{breakout_id}\n{project_id}\n{timestamp}\n{file_sha256}"
    return hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def _flip_last_hex_char(sig: str) -> str:
    last = sig[-1]
    replacement = "0" if last != "0" else "1"
    return sig[:-1] + replacement


def main() -> int:
    parser = argparse.ArgumentParser(description="POST an MP4 to the bridge, mimicking Frankly.")
    parser.add_argument("--file", required=True, type=Path, help="Path to MP4 (or audio) file.")
    parser.add_argument("--event-id", required=True, help="Frankly event identifier.")
    parser.add_argument("--breakout-id", required=True, help="Frankly breakout room identifier.")
    parser.add_argument("--project-id", required=True, help="Dembrane project identifier.")
    parser.add_argument(
        "--timestamp",
        default=None,
        help="ISO 8601 timestamp. Default: current UTC time.",
    )
    parser.add_argument(
        "--bad-hmac",
        action="store_true",
        help="Flip the last hex char of the signature so the bridge rejects it.",
    )
    args = parser.parse_args()

    secret = os.environ.get("BRIDGE_HMAC_SECRET")
    if not secret:
        print("error: BRIDGE_HMAC_SECRET environment variable is not set", file=sys.stderr)
        return 2

    bridge_url = os.environ.get("BRIDGE_URL", "http://localhost:8100")

    if not args.file.exists():
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 2

    timestamp = args.timestamp or datetime.now(timezone.utc).isoformat()

    sig = compute_signature(args.event_id, args.breakout_id, args.project_id, timestamp, args.file, secret)
    if args.bad_hmac:
        sig = _flip_last_hex_char(sig)

    print(f"[script] POST {bridge_url}/recordings/incoming")
    print(f"[script] event_id={args.event_id} breakout_id={args.breakout_id} timestamp={timestamp}")
    print(f"[script] project_id={args.project_id}")
    print(f"[script] file={args.file} ({args.file.stat().st_size} bytes)")
    print(f"[script] hmac_signature={sig}{' (CORRUPTED)' if args.bad_hmac else ''}")

    with open(args.file, "rb") as f:
        response = httpx.post(
            f"{bridge_url}/recordings/incoming",
            data={
                "event_id": args.event_id,
                "breakout_id": args.breakout_id,
                "project_id": args.project_id,
                "timestamp": timestamp,
                "hmac_signature": sig,
            },
            files={"file": (args.file.name, f, "video/mp4")},
            timeout=300.0,
        )

    print(f"[script] response: HTTP {response.status_code}")
    print(f"[script] body: {response.text}")
    if response.status_code == 202:
        print("[script] check the uvicorn terminal for pipeline progress.")

    expected_status = (400,) if args.bad_hmac else (202,)
    return 0 if response.status_code in expected_status else 1


if __name__ == "__main__":
    sys.exit(main())
