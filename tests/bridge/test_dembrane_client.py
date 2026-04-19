import httpx
import respx
from bridge.dembrane_client import initiate_conversation, upload_chunk, finish_conversation


@respx.mock
async def test_initiate_conversation_returns_id():
    respx.post("https://api.dembrane.com/api/participant/projects/proj-1/conversations/initiate").mock(
        return_value=httpx.Response(200, json={
            "id": "conv-abc",
            "project_id": "proj-1",
        })
    )
    result = await initiate_conversation("proj-1", "event-1 / room-2")
    assert result == "conv-abc"


@respx.mock
async def test_initiate_conversation_raises_on_error():
    respx.post("https://api.dembrane.com/api/participant/projects/proj-1/conversations/initiate").mock(
        return_value=httpx.Response(500)
    )
    try:
        await initiate_conversation("proj-1", "event-1 / room-2")
        assert False, "should have raised"
    except httpx.HTTPStatusError:
        pass


@respx.mock
async def test_upload_chunk_calls_all_three_steps(tmp_path):
    chunk = tmp_path / "chunk_000.webm"
    chunk.write_bytes(b"audio data")

    respx.post(
        "https://api.dembrane.com/api/participant/conversations/conv-1/get-upload-url"
    ).mock(return_value=httpx.Response(200, json={
        "chunk_id": "chk-1",
        "upload_url": "https://s3.example.com/upload",
        "fields": {"acl": "private", "key": "some/path.webm"},
        "file_url": "https://s3.example.com/file.webm",
    }))
    respx.post("https://s3.example.com/upload").mock(return_value=httpx.Response(204))
    respx.post(
        "https://api.dembrane.com/api/participant/conversations/conv-1/confirm-upload"
    ).mock(return_value=httpx.Response(200, json={"id": "confirmed"}))

    await upload_chunk("conv-1", chunk, "2026-04-19T10:00:00Z")

    assert respx.calls.call_count == 3


@respx.mock
async def test_finish_conversation(tmp_path):
    respx.post(
        "https://api.dembrane.com/api/participant/conversations/conv-1/finish"
    ).mock(return_value=httpx.Response(200, json={}))

    await finish_conversation("conv-1")

    assert respx.calls.call_count == 1
