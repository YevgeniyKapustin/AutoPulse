"""Source adapter registry."""

from __future__ import annotations

from collections.abc import Mapping

from services.crawler.app.adapters.copart import CopartAdapter
from services.crawler.app.adapters.iaai import IaaiAdapter
from services.crawler.app.adapters.manual import ManualAdapter
from services.crawler.app.adapters.ports import SourceAdapter
from services.crawler.app.core.exceptions import UnknownSourceError


def default_adapters() -> dict[str, SourceAdapter]:
    copart = CopartAdapter()
    iaai = IaaiAdapter()
    manual = ManualAdapter()
    return {
        copart.source.value: copart,
        iaai.source.value: iaai,
        manual.source.value: manual,
    }


class AdapterRegistry:
    def __init__(self, adapters: Mapping[str, SourceAdapter] | None = None) -> None:
        self._adapters = dict(adapters or default_adapters())

    def get(self, source: str) -> SourceAdapter:
        key = source.strip().lower()
        try:
            return self._adapters[key]
        except KeyError as exc:
            known = ", ".join(sorted(self._adapters))
            raise UnknownSourceError(
                f"unknown source {source!r}; known: {known}"
            ) from exc

    def names(self) -> list[str]:
        return sorted(self._adapters)
