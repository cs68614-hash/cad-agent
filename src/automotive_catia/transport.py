"""Streamable HTTP transport. Authentication is not encryption: use a TLS proxy/VPN."""
from __future__ import annotations

import hmac
import ipaddress
from dataclasses import dataclass, field
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from .server import close_coordinator, create_server


def is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class HTTPSettings:
    host: str = "127.0.0.1"
    port: int = 8765
    token: str | None = field(default=None, repr=False)
    allowed_hosts: tuple[str, ...] = ()
    allowed_origins: tuple[str, ...] = ()

    def __post_init__(self):
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if not is_loopback(self.host):
            if not self.token or len(self.token) < 32:
                raise ValueError("non-loopback HTTP requires AUTO_CATIA_TOKEN of at least 32 characters")
            if not self.allowed_hosts:
                raise ValueError("non-loopback HTTP requires explicit --allowed-host values (host:port)")
        if any("*" in item for item in self.allowed_hosts + self.allowed_origins):
            raise ValueError("wildcard hosts and origins are forbidden")

    @property
    def hosts(self) -> list[str]:
        return list(self.allowed_hosts) or [
            f"127.0.0.1:{self.port}", f"localhost:{self.port}", f"[::1]:{self.port}"
        ]


async def reject(send, status: int, message: str):
    body = message.encode("utf-8")
    headers = [(b"content-type", b"text/plain; charset=utf-8"), (b"cache-control", b"no-store")]
    if status == 401:
        headers.append((b"www-authenticate", b"Bearer"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class HTTPApp:
    def __init__(self, coordinator, settings: HTTPSettings):
        self.coordinator = coordinator
        self.settings = settings
        self.server = create_server(coordinator)
        self.manager = StreamableHTTPSessionManager(
            app=self.server,
            json_response=True,
            stateless=False,
            security_settings=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=settings.hosts,
                allowed_origins=list(settings.allowed_origins),
            ),
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            async with self.manager.run():
                while True:
                    event = await receive()
                    if event["type"] == "lifespan.startup":
                        await send({"type": "lifespan.startup.complete"})
                    elif event["type"] == "lifespan.shutdown":
                        await close_coordinator(self.coordinator)
                        await send({"type": "lifespan.shutdown.complete"})
                        return
            return
        if scope["type"] != "http":
            return
        if scope.get("path") != "/mcp":
            return await reject(send, 404, "Not found")
        # Check here as well as in SDK, before allocating protocol sessions.
        headers = {}
        for key, value in scope.get("headers", []):
            key = key.lower()
            if key in headers and key in {b"authorization", b"host", b"origin"}:
                return await reject(send, 400, "Duplicate security header")
            headers[key] = value
        host = headers.get(b"host", b"").decode("latin1")
        origin = headers.get(b"origin", b"").decode("latin1")
        if host not in self.settings.hosts:
            return await reject(send, 421, "Host is not allowed")
        if origin and origin not in self.settings.allowed_origins:
            return await reject(send, 403, "Origin is not allowed")
        token = self.settings.token
        if token:
            expected = b"Bearer " + token.encode("utf-8")
            if not hmac.compare_digest(headers.get(b"authorization", b""), expected):
                return await reject(send, 401, "Bearer authentication required")
        if scope.get("method") not in {"GET", "POST", "DELETE"}:
            return await reject(send, 405, "Method not allowed")
        await self.manager.handle_request(scope, receive, send)


def create_http_app(coordinator, settings: HTTPSettings):
    return HTTPApp(coordinator, settings)
