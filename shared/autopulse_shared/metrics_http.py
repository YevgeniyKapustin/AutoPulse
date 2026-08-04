"""Scrape-only HTTP server for Prometheus text metrics.

Binds a dedicated port (not the public API) so reverse proxies can exclude it
and clients never see /metrics on the application port.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Final

logger = logging.getLogger(__name__)

_CONTENT_TYPE: Final = b"text/plain; version=0.0.4; charset=utf-8"
_READ_TIMEOUT_SEC: Final = 5.0


class MetricsHttpServer:
    """Minimal GET /metrics server using asyncio streams (no extra deps)."""

    def __init__(
        self,
        *,
        render: Callable[[], str],
        host: str = "0.0.0.0",
        port: int = 9090,
    ) -> None:
        """Create a server that serves ``render()`` at GET /metrics."""
        self._render: Callable[[], str] = render
        self._host: str = host
        self._port: int = port
        self._server: asyncio.AbstractServer | None = None

    @property
    def port(self) -> int:
        """Bound port (usable after ``start``; supports ``port=0``)."""
        if self._server is None or not self._server.sockets:
            return self._port
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        """Listen on ``host:port`` for Prometheus scrapes."""
        self._server = await asyncio.start_server(
            self._handle,
            self._host,
            self._port,
        )
        sockets = self._server.sockets or []
        bound = ", ".join(str(sock.getsockname()) for sock in sockets)
        logger.info("Metrics scrape endpoint listening on %s", bound)

    async def stop(self) -> None:
        """Close the listen socket and wait until all connections finish."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            try:
                raw = await asyncio.wait_for(
                    reader.readuntil(b"\r\n\r\n"),
                    timeout=_READ_TIMEOUT_SEC,
                )
            except (
                asyncio.IncompleteReadError,
                asyncio.TimeoutError,
                ConnectionError,
            ):
                return

            request_line = raw.split(b"\r\n", 1)[0].decode(
                "latin-1",
                errors="replace",
            )
            parts = request_line.split()
            method = parts[0] if parts else ""
            path = parts[1].split("?", 1)[0] if len(parts) >= 2 else "/"

            if method == "GET" and path == "/metrics":
                body = self._render().encode("utf-8")
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: "
                    + _CONTENT_TYPE
                    + b"\r\n"
                    b"Content-Length: "
                    + str(len(body)).encode("ascii")
                    + b"\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                    + body
                )
            else:
                body = b"Not Found\n"
                writer.write(
                    b"HTTP/1.1 404 Not Found\r\n"
                    b"Content-Type: text/plain; charset=utf-8\r\n"
                    b"Content-Length: "
                    + str(len(body)).encode("ascii")
                    + b"\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                    + body
                )
            await writer.drain()
        finally:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
