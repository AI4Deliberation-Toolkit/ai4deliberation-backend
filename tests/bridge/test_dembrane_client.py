import httpx
import respx
from bridge.dembrane_client import initiate_conversation


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
