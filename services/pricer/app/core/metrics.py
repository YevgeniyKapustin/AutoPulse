"""Lightweight process metrics (Prometheus text exposition)."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = (
            defaultdict(float)
        )
        self._lock = Lock()

    def inc(self, name: str, amount: float = 1.0, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] += amount

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            items = list(self._counters.items())
        for (name, labels), value in sorted(items):
            if labels:
                label_str = ",".join(f'{k}="{v}"' for k, v in labels)
                lines.append(f"{name}{{{label_str}}} {value}")
            else:
                lines.append(f"{name} {value}")
        lines.append("")
        return "\n".join(lines)


METRICS = MetricsRegistry()
