"""Offline tests for the command line, above all `--healthcheck`.

The container runs `systembolaget-mcp --healthcheck` every 30 s, so it has to stay a
bare TCP connect: it must not import the server (httpx, pydantic, mcp) or even argparse.
"""

import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import systembolaget_cli as cli
import systembolaget_mcp as sb

ROOT = Path(__file__).parent
HEAVY_MODULES = ("argparse", "httpx", "pydantic", "mcp", "systembolaget_mcp")


@pytest.fixture
def listening_port() -> Iterator[int]:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        yield server.getsockname()[1]


@pytest.fixture
def closed_port() -> int:
    """A port nothing listens on (bound once to get a free one, then released)."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in ("TRANSPORT", "HOST", "PORT"):
        monkeypatch.delenv(f"SYSTEMBOLAGET_MCP_{name}", raising=False)
    return monkeypatch


def test_healthcheck_succeeds_when_something_listens(listening_port: int) -> None:
    assert cli.main(["--healthcheck", "--port", str(listening_port)]) is None


def test_healthcheck_exits_1_when_nothing_listens(closed_port: int) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--healthcheck", "--port", str(closed_port)])
    assert exit_info.value.code == 1


def test_healthcheck_port_defaults_to_env(
    clean_env: pytest.MonkeyPatch, listening_port: int, closed_port: int
) -> None:
    clean_env.setenv("SYSTEMBOLAGET_MCP_PORT", str(listening_port))
    assert cli.main(["--healthcheck"]) is None

    clean_env.setenv("SYSTEMBOLAGET_MCP_PORT", str(closed_port))
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--healthcheck"])
    assert exit_info.value.code == 1


@pytest.mark.parametrize(
    "argv",
    [
        ["--healthcheck", "--port", "{port}"],
        ["--port", "{port}", "--healthcheck"],
        ["--healthcheck", "--port={port}"],
        ["--healthc", "--port", "{port}"],  # abbreviation: not the fast path, argparse
    ],
)
def test_healthcheck_argument_forms(argv: list[str], listening_port: int, closed_port: int) -> None:
    assert cli.main([a.format(port=listening_port) for a in argv]) is None
    with pytest.raises(SystemExit) as exit_info:
        cli.main([a.format(port=closed_port) for a in argv])
    assert exit_info.value.code == 1


def test_healthcheck_bad_port_is_an_argparse_error() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--healthcheck", "--port", "abc"])
    assert exit_info.value.code == 2


def test_healthcheck_port_out_of_range_fails() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--healthcheck", "--port", "99999"])
    assert exit_info.value.code == 1


def test_healthcheck_does_not_import_the_server(listening_port: int, closed_port: int) -> None:
    """A fresh interpreter: pytest itself has the server modules loaded already."""
    code = f"""
import sys
import systembolaget_cli
status = 0
try:
    systembolaget_cli.main(["--healthcheck", "--port", sys.argv[1]])
except SystemExit as exc:
    status = exc.code
print(status, [m for m in {HEAVY_MODULES!r} if m in sys.modules])
"""
    for port, expected_status in ((listening_port, 0), (closed_port, 1)):
        result = subprocess.run(
            [sys.executable, "-c", code, str(port)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == f"{expected_status} []"


def test_defaults_to_stdio(clean_env: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, int]] = []
    cli.main([], serve=lambda *args: calls.append(args))
    assert calls == [("stdio", "127.0.0.1", 8000)]


def test_server_options_from_command_line(clean_env: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, int]] = []
    cli.main(
        ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "9000"],
        serve=lambda *args: calls.append(args),
    )
    assert calls == [("streamable-http", "0.0.0.0", 9000)]


def test_server_options_from_env(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("SYSTEMBOLAGET_MCP_TRANSPORT", "streamable-http")
    clean_env.setenv("SYSTEMBOLAGET_MCP_HOST", "0.0.0.0")
    clean_env.setenv("SYSTEMBOLAGET_MCP_PORT", "8123")
    calls: list[tuple[str, str, int]] = []
    cli.main([], serve=lambda *args: calls.append(args))
    assert calls == [("streamable-http", "0.0.0.0", 8123)]


@pytest.fixture
def mcp_run(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    """Replace the blocking server loop; record how it was started."""
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(sb.mcp, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    return calls


def test_serve_stdio(mcp_run: list[tuple[tuple[Any, ...], dict[str, Any]]]) -> None:
    sb.serve("stdio", "127.0.0.1", 8000)
    assert mcp_run == [(("stdio",), {})]


def test_serve_streamable_http(mcp_run: list[tuple[tuple[Any, ...], dict[str, Any]]]) -> None:
    sb.serve("streamable-http", "0.0.0.0", 8000)
    assert mcp_run == [
        (("streamable-http",), {"host": "0.0.0.0", "port": 8000, "stateless_http": True})
    ]


def test_console_script_path_starts_the_server(
    clean_env: pytest.MonkeyPatch, mcp_run: list[tuple[tuple[Any, ...], dict[str, Any]]]
) -> None:
    """`systembolaget-mcp` (no flags) imports the server lazily and runs it on stdio."""
    cli.main([])
    assert mcp_run == [(("stdio",), {})]


def test_script_path_starts_the_server(
    clean_env: pytest.MonkeyPatch, mcp_run: list[tuple[tuple[Any, ...], dict[str, Any]]]
) -> None:
    """`python systembolaget_mcp.py --transport ...` goes through the same parser."""
    clean_env.setattr(sys, "argv", ["systembolaget_mcp.py", "--transport", "streamable-http"])
    sb.main()
    assert mcp_run == [
        (("streamable-http",), {"host": "127.0.0.1", "port": 8000, "stateless_http": True})
    ]
