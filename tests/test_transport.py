"""Offline ASGI security and real MCP transport integration checks; no live COM."""
import asyncio
import unittest
from automotive_catia.server import result_to_mcp, create_server
from automotive_catia.transport import HTTPSettings, create_http_app


class FakeCoordinator:
    def list_tools(self):
        return [{"name": "inspect", "description": "Offline probe", "inputSchema": {"type": "object"}}]

    async def call(self, name, args):
        return {"ok": True, "data": args, "mock": True}

    def close(self):
        pass


class TransportTests(unittest.TestCase):
    def test_loopback_default(self):
        self.assertEqual(HTTPSettings().host, "127.0.0.1")

    def test_remote_requires_token(self):
        with self.assertRaises(ValueError):
            HTTPSettings(host="0.0.0.0", allowed_hosts=("worker:8765",))

    def test_remote_requires_hosts(self):
        with self.assertRaises(ValueError):
            HTTPSettings(host="0.0.0.0", token="x" * 32)

    def test_no_wildcards(self):
        with self.assertRaises(ValueError):
            HTTPSettings(allowed_hosts=("*",))

    def test_failure_is_mcp_error(self):
        result = result_to_mcp({"ok": False, "error": {"code": "FEATURE_NO_EFFECT"}})
        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["error"]["code"], "FEATURE_NO_EFFECT")

    def test_unknown_is_mcp_error(self):
        self.assertTrue(result_to_mcp({"status": "unknown_outcome"}).isError)


class SecurityTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, headers, path="/mcp", method="POST", settings=None):
        app = create_http_app(FakeCoordinator(), settings or HTTPSettings(token="x" * 32))
        events = []
        async def receive():
            return {"type": "http.request", "body": b"{}", "more_body": False}
        async def send(event):
            events.append(event)
        await app({"type": "http", "path": path, "method": method, "headers": headers}, receive, send)
        return events[0]["status"]

    async def test_missing_token(self):
        self.assertEqual(await self.request([(b"host", b"127.0.0.1:8765")]), 401)

    async def test_wrong_token(self):
        self.assertEqual(await self.request([(b"host", b"127.0.0.1:8765"), (b"authorization", b"Bearer wrong")]), 401)

    async def test_rebinding_host(self):
        self.assertEqual(await self.request([(b"host", b"evil.example")]), 421)

    async def test_browser_origin(self):
        self.assertEqual(await self.request([(b"host", b"127.0.0.1:8765"), (b"origin", b"https://evil.example")]), 403)

    async def test_duplicate_authorization(self):
        self.assertEqual(await self.request([(b"host", b"127.0.0.1:8765"), (b"authorization", b"a"), (b"authorization", b"b")]), 400)

    async def test_unknown_path(self):
        self.assertEqual(await self.request([], path="/"), 404)

    async def test_method_restricted(self):
        self.assertEqual(await self.request([(b"host", b"127.0.0.1:8765")], method="PUT", settings=HTTPSettings()), 405)

    async def test_actual_streamable_http_client_in_memory(self):
        """SDK client initialize/list/call over ASGI; no TCP listener created."""
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        app = create_http_app(FakeCoordinator(), HTTPSettings(token="x" * 32))
        async with app.manager.run():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                headers={"Authorization": "Bearer " + "x" * 32},
            ) as http_client:
                async with streamable_http_client(
                    "http://127.0.0.1:8765/mcp", http_client=http_client,
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        listed = await session.list_tools()
                        self.assertEqual([t.name for t in listed.tools], ["inspect"])
                        result = await session.call_tool("inspect", {"probe": 1})
                        self.assertFalse(result.isError)
                        self.assertEqual(result.structuredContent["data"], {"probe": 1})


class StdioIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_stdio_client_mock_catalog_and_session(self):
        import os
        import sys
        import tempfile
        from pathlib import Path
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        source = str(Path(__file__).resolve().parents[1] / "src")
        with tempfile.TemporaryDirectory(prefix="automotive-catia-stdio-") as workspace:
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "automotive_catia", "--mock", "--workspace", workspace],
                env={**os.environ, "PYTHONPATH": source},
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    self.assertEqual(len(listed.tools), 159)
                    names = [tool.name for tool in listed.tools]
                    self.assertEqual(len(names), len(set(names)))
                    self.assertIn("auto_session", names)
                    result = await session.call_tool("auto_session", {})
                    self.assertFalse(result.isError)
                    self.assertTrue(result.structuredContent["mock"])
                    self.assertTrue(result.structuredContent["ok"])


if __name__ == "__main__":
    unittest.main()
