import json
from decouple import config

HMAC_SECRET: str = config("BRIDGE_HMAC_SECRET")
DEMBRANE_BASE_URL: str = config("DEMBRANE_BASE_URL", default="https://api.dembrane.com")
DEMBRANE_API_KEY: str = config("DEMBRANE_API_KEY", default="")


# Currently unused in the request path. Reserved for an optional defense-in-depth
# check where the bridge enforces a known event→project mapping. See bridge/INTEGRATION.md
# Design notes.
def get_project_id(event_id: str) -> str | None:
    raw = config("DEMBRANE_PROJECT_MAP", default="{}")
    mapping: dict[str, str] = json.loads(raw)
    return mapping.get(event_id)
