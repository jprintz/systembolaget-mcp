"""Command-line entry point of the Systembolaget MCP server (`systembolaget-mcp`).

The container health check runs `systembolaget-mcp --healthcheck` every 30 s, so
this module stays cheap to import: no httpx, pydantic or mcp (the server module is
imported only once a server is actually started), and not even argparse for a plain
health check. The slim container image ships no stdlib bytecode, so every module
imported costs a compile on every run. Keep new imports out of the health check path.
"""

from __future__ import annotations

import os
import socket
import sys
from collections.abc import Callable, Sequence

TYPE_CHECKING = False  # as typing.TYPE_CHECKING, without importing typing
if TYPE_CHECKING:
    import argparse

HEALTHCHECK_TIMEOUT = 2.0  # seconds


def build_parser() -> argparse.ArgumentParser:
    import argparse

    parser = argparse.ArgumentParser(
        prog="systembolaget-mcp",
        description=(
            "Run the MCP server. stdio by default (Claude Desktop and other local clients). "
            "As a remote server: --transport streamable-http --host 0.0.0.0 --port 8000, or "
            "the same through SYSTEMBOLAGET_MCP_TRANSPORT / _HOST / _PORT. The endpoint is "
            "/mcp. --healthcheck exits 0 when the HTTP server accepts connections."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.getenv("SYSTEMBOLAGET_MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.getenv("SYSTEMBOLAGET_MCP_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("SYSTEMBOLAGET_MCP_PORT", "8000"))
    )
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help="exit 0 if the HTTP server accepts connections (container health checks)",
    )
    return parser


def healthcheck(port: int) -> bool:
    """True if something accepts TCP connections on 127.0.0.1:<port>."""
    # connect() takes the IPv4 literal as is; socket.create_connection would first
    # resolve it, which imports the IDNA codec.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(HEALTHCHECK_TIMEOUT)
        try:
            sock.connect(("127.0.0.1", port))
        except (OSError, OverflowError):  # refused, unreachable, timed out, port out of range
            return False
    return True


def plain_healthcheck_port(argv: Sequence[str]) -> int | None:
    """The port to check if `argv` is a plain health check, else None.

    Recognizes `--healthcheck` with an optional `--port N` or `--port=N` (the port
    defaults to SYSTEMBOLAGET_MCP_PORT, else 8000) and nothing else. Anything
    different, such as other flags, abbreviations or a bad value, is left to
    argparse, which handles it and reports the errors.
    """
    rest = list(argv)
    if "--healthcheck" not in rest:
        return None
    rest.remove("--healthcheck")
    try:
        if not rest:
            return int(os.getenv("SYSTEMBOLAGET_MCP_PORT", "8000"))
        if len(rest) == 2 and rest[0] == "--port":
            return int(rest[1])
        if len(rest) == 1 and rest[0].startswith("--port="):
            return int(rest[0].removeprefix("--port="))
    except ValueError:
        pass
    return None


def main(
    argv: Sequence[str] | None = None,
    serve: Callable[[str, str, int], None] | None = None,
) -> None:
    """Parse the command line, then run the health check or start the server.

    `serve(transport, host, port)` starts the server; by default it is imported
    from systembolaget_mcp, which `python systembolaget_mcp.py` overrides with
    its own (already loaded) copy rather than importing the module twice.
    """
    if argv is None:
        argv = sys.argv[1:]

    health_port = plain_healthcheck_port(argv)
    if health_port is None:
        args = build_parser().parse_args(argv)
        if not args.healthcheck:
            if serve is None:
                from systembolaget_mcp import serve as default_serve

                serve = default_serve
            serve(args.transport, args.host, args.port)
            return
        health_port = args.port

    if not healthcheck(health_port):
        sys.exit(1)


if __name__ == "__main__":
    main()
