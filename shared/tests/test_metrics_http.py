"""Tests for the scrape-only metrics HTTP server."""

from __future__ import annotations

import asyncio

from autopulse_shared.metrics_http import MetricsHttpServer


async def _get(host: str, port: int, path: str) -> tuple[int, bytes]:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(f"GET {path} HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=2.0)
    finally:
        writer.close()
        await writer.wait_closed()
    header, _, body = raw.partition(b"\r\n\r\n")
    status = int(header.split(b" ", 2)[1])
    return status, body


async def test_metrics_path_returns_body() -> None:
    server = MetricsHttpServer(
        render=lambda: "# HELP demo\ndemo 1\n",
        host="127.0.0.1",
        port=0,
    )
    await server.start()
    try:
        status, body = await _get("127.0.0.1", server.port, "/metrics")
        assert status == 200
        assert b"demo 1" in body
    finally:
        await server.stop()


async def test_other_paths_are_404() -> None:
    server = MetricsHttpServer(
        render=lambda: "ok\n",
        host="127.0.0.1",
        port=0,
    )
    await server.start()
    try:
        status, body = await _get("127.0.0.1", server.port, "/health")
        assert status == 404
        assert b"Not Found" in body
    finally:
        await server.stop()
