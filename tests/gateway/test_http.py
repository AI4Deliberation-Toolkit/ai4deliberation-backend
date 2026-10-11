import gc
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from gateway import http


class _OkHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'  # keep-alive: a pooled connection would be reused across loops

    def do_GET(self):
        body = b'ok'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class PerLoopClientTests(SimpleTestCase):
    def setUp(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), _OkHandler)  # loopback only
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.url = f'http://127.0.0.1:{server.server_port}/'

    def test_two_fresh_event_loops_both_succeed(self):
        # Each async_to_sync call runs in a new event loop. A single shared client would fail the
        # second call with "RuntimeError: Event loop is closed" (review 2026-10-11, finding 1).
        async def fetch():
            return (await http.get_client().get(self.url)).status_code

        self.assertEqual(async_to_sync(fetch)(), 200)
        self.assertEqual(async_to_sync(fetch)(), 200)

    def test_clients_of_closed_loops_are_freed(self):
        async def fetch():
            return (await http.get_client().get(self.url)).status_code

        for _ in range(3):
            async_to_sync(fetch)()
        gc.collect()
        self.assertLessEqual(len(http._clients), 1)

    def test_one_client_per_loop(self):
        async def same():
            return http.get_client() is http.get_client()

        self.assertTrue(async_to_sync(same)())

    def test_client_does_not_follow_redirects_and_has_no_default_timeout(self):
        async def config():
            client = http.get_client()
            return client.follow_redirects, client.timeout

        follow, timeout = async_to_sync(config)()
        self.assertFalse(follow)
        self.assertEqual(timeout, httpx.Timeout(None))

    def test_sync_client(self):
        client = http.build_sync_client(timeout=10)
        self.assertFalse(client.follow_redirects)
        self.assertEqual(client.timeout, httpx.Timeout(10))
