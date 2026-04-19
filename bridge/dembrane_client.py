import httpx
from bridge.config import DEMBRANE_BASE_URL, DEMBRANE_API_KEY


def _headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if DEMBRANE_API_KEY:
        headers["Authorization"] = f"Bearer {DEMBRANE_API_KEY}"
    return headers


async def initiate_conversation(project_id: str, name: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{DEMBRANE_BASE_URL}/api/participant/projects/{project_id}/conversations/initiate",
            json={
                "name": name,
                "pin": "",
                "source": "AI4D_BRIDGE",
                "tag_id_list": [],
                "user_agent": "ai4d-bridge/1.0",
            },
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()["id"]
