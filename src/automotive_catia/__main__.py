"""Command-line entry point. Importing this module never connects to CATIA."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Automotive CATIA MCP — Windows worker; stdio or Streamable HTTP")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--workspace", type=Path, default=Path.cwd() / "workspace")
    parser.add_argument("--mock", action="store_true", help="Offline simulated backend; never contacts CATIA")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--allowed-host", action="append", default=[], help="Exact HTTP Host, including port when present")
    parser.add_argument("--allowed-origin", action="append", default=[], help="Exact trusted browser origin; default denies all")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)  # stderr only; stdout is MCP protocol.
    from .coordinator import Coordinator
    if args.transport == "http":
        from .transport import HTTPSettings, create_http_app
        settings = HTTPSettings(
            host=args.host, port=args.port, token=os.environ.get("AUTO_CATIA_TOKEN"),
            allowed_hosts=tuple(args.allowed_host), allowed_origins=tuple(args.allowed_origin),
        )
        coordinator = Coordinator(workspace=args.workspace, mock=args.mock)
        import uvicorn
        uvicorn.run(create_http_app(coordinator, settings), host=settings.host,
                    port=settings.port, proxy_headers=False, access_log=False)
    else:
        from .server import serve_stdio
        asyncio.run(serve_stdio(Coordinator(workspace=args.workspace, mock=args.mock)))


if __name__ == "__main__":
    main()
