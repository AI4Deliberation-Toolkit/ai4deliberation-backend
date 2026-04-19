import httpx
from pathlib import Path
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


async def upload_chunk(conversation_id: str, chunk_path: Path, timestamp: str) -> None:
    async with httpx.AsyncClient() as client:
        # Step 1: get presigned upload URL
        r = await client.post(
            f"{DEMBRANE_BASE_URL}/api/participant/conversations/{conversation_id}/get-upload-url",
            json={
                "content_type": "audio/webm",
                "conversation_id": conversation_id,
                "filename": chunk_path.name,
            },
            headers=_headers(),
        )
        r.raise_for_status()
        data = r.json()
        chunk_id: str = data["chunk_id"]
        upload_url: str = data["upload_url"]
        fields: dict = data["fields"]
        file_url: str = data["file_url"]

        # Step 2: upload to S3 presigned endpoint
        with open(chunk_path, "rb") as f:
            s3_response = await client.post(
                upload_url,
                data=fields,
                files={"file": (chunk_path.name, f, "audio/webm")},
            )
        s3_response.raise_for_status()

        # Step 3: confirm upload with dembrane
        confirm = await client.post(
            f"{DEMBRANE_BASE_URL}/api/participant/conversations/{conversation_id}/confirm-upload",
            json={
                "chunk_id": chunk_id,
                "file_url": file_url,
                "source": "AI4D_BRIDGE",
                "timestamp": timestamp,
            },
            headers=_headers(),
        )
        confirm.raise_for_status()


async def finish_conversation(conversation_id: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{DEMBRANE_BASE_URL}/api/participant/conversations/{conversation_id}/finish",
            headers=_headers(),
        )
        response.raise_for_status()
