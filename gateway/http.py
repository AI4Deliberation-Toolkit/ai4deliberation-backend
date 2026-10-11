"""The gateway's outbound HTTP clients. Tests replace these factories."""
import asyncio
import weakref

import httpx

_clients: 'weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient]' = weakref.WeakKeyDictionary()


def get_client() -> httpx.AsyncClient:
    """One pooled client per running event loop.

    Under uvicorn workers that is one per process. Anything that runs a view in a fresh loop
    (WSGI, async_to_sync) gets its own client, instead of a pooled connection bound to a closed loop.
    No default timeout (invoke passes each tool's timeout_seconds); redirects are never followed.
    """
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None:
        client = _clients[loop] = httpx.AsyncClient(follow_redirects=False, timeout=None)
    return client


def build_sync_client(timeout: float) -> httpx.Client:
    """For management commands (check_tools)."""
    return httpx.Client(follow_redirects=False, timeout=timeout)
