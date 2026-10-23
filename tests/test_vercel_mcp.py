import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "example"))

from server import mcp
from vercel_mcp import restore_path, serverless_app, vercel_hosts

HOST = "my-app-git-main-team.vercel.app"
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}


def call(app, method, url, body=None, host=HOST):
    path, _, query = url.partition("?")
    data = json.dumps(body).encode() if body is not None else b""
    headers = [(b"host", host.encode()), (b"accept", b"application/json, text/event-stream")]
    if body is not None:
        headers.append((b"content-type", b"application/json"))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "https",
             "path": path, "raw_path": path.encode(), "query_string": query.encode(), "root_path": "",
             "headers": headers, "client": ("1.2.3.4", 1), "server": (host, 443)}
    out = {"status": None, "body": b""}
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": data, "more_body": False}
        await asyncio.sleep(3600)

    async def send(msg):
        if msg["type"] == "http.response.start":
            out["status"] = msg["status"]
        elif msg["type"] == "http.response.body":
            out["body"] += msg.get("body", b"")

    asyncio.run(app(scope, receive, send))
    return out["status"], out["body"]


class RestorePath(unittest.TestCase):
    def test_original_path_comes_back_and_other_params_survive(self):
        s = restore_path({"path": "/api/index", "query_string": b"__path=/static/a%20b.js&v=2"})
        self.assertEqual((s["path"], s["query_string"]), ("/static/a b.js", b"v=2"))

    def test_untouched_without_param(self):
        scope = {"path": "/mcp", "query_string": b"x=1"}
        self.assertIs(restore_path(scope), scope)


class ServerlessApp(unittest.TestCase):
    def setUp(self):
        self.app = serverless_app(mcp)

    def test_without_the_adapter_every_rewritten_url_is_not_found(self):
        plain = mcp.streamable_http_app(stateless_http=True, json_response=True, host="0.0.0.0")

        async def raw(scope, receive, send):
            async with plain.router.lifespan_context(plain):
                await plain(scope, receive, send)
        self.assertEqual(call(raw, "GET", "/api/index?__path=/")[0], 404)

    def test_custom_route_is_reached(self):
        status, body = call(self.app, "GET", "/api/index?__path=/")
        self.assertEqual(status, 200)
        self.assertIn(b"hello-vercel", body)

    def test_initialize_on_a_vercel_host(self):
        status, body = call(self.app, "POST", "/api/index?__path=/mcp", INIT)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["result"]["protocolVersion"], "2025-11-25")

    def test_requests_stand_alone_without_a_session(self):
        for i in range(3):
            status, body = call(self.app, "POST", "/api/index?__path=/mcp",
                                {"jsonrpc": "2.0", "id": i, "method": "tools/call",
                                 "params": {"name": "greet", "arguments": {"name": f"n{i}"}}})
            self.assertEqual(status, 200)
            self.assertIn(f"Hello, n{i}!", body.decode())

    def test_tools_list(self):
        _, body = call(self.app, "POST", "/api/index?__path=/mcp", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual({t["name"] for t in json.loads(body)["result"]["tools"]}, {"greet", "add"})

    def test_allowed_hosts_keeps_rebinding_protection(self):
        strict = serverless_app(mcp, allowed_hosts=[HOST])
        self.assertEqual(call(strict, "POST", "/api/index?__path=/mcp", INIT)[0], 200)
        self.assertEqual(call(strict, "POST", "/api/index?__path=/mcp", INIT, host="evil.example")[0], 421)

    def test_lifespan_is_answered(self):
        msgs = iter([{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}])
        sent = []

        async def receive():
            return next(msgs)

        async def send(m):
            sent.append(m["type"])
        asyncio.run(self.app({"type": "lifespan"}, receive, send))
        self.assertEqual(sent, ["lifespan.startup.complete", "lifespan.shutdown.complete"])


class Hosts(unittest.TestCase):
    def test_vercel_hosts_reads_system_env(self):
        import os
        os.environ.update(VERCEL_URL="a-123.vercel.app", VERCEL_PROJECT_PRODUCTION_URL="a.vercel.app")
        self.assertEqual(vercel_hosts(), ["a-123.vercel.app", "a.vercel.app"])


if __name__ == "__main__":
    unittest.main()
