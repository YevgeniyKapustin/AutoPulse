"""RabbitMQ Management API probe for queue depths."""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Self
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class RabbitQueueStats:
    """Read queue message counts via the Management HTTP API."""

    def __init__(
        self,
        base_url: str,
        *,
        username: str,
        password: str,
        vhost: str = "/",
        timeout_sec: float = 2.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._vhost = quote(vhost if vhost else "/", safe="")
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=self._base_url,
            auth=(username, password),
            timeout=timeout_sec,
        )

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def depths(self, queue_names: list[str]) -> dict[str, int | None]:
        result: dict[str, int | None] = {}
        for name in queue_names:
            result[name] = await self._depth(name)
        return result

    async def _depth(self, queue_name: str) -> int | None:
        path = f"/api/queues/{self._vhost}/{quote(queue_name, safe='')}"
        try:
            response = await self._http.get(path)
            if response.status_code == 404:
                return 0
            response.raise_for_status()
            payload = response.json()
            messages = payload.get("messages")
            if isinstance(messages, int):
                return messages
            return None
        except Exception as exc:
            logger.warning("Rabbit queue depth failed queue=%s: %s", queue_name, exc)
            return None
