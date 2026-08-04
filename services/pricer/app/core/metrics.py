"""Lightweight process metrics (Prometheus text exposition)."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Protocol


class MetricsRecorder(Protocol):
    def inc(self, name: str, amount: float = 1.0, **labels: str) -> None: ...


class MetricsRegistry:
    """In-process counter registry with Prometheus text exposition."""

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
        declared: set[str] = set()
        for (name, labels), value in sorted(items):
            if name not in declared:
                lines.append(f"# HELP {name} AutoPulse counter.")
                lines.append(f"# TYPE {name} counter")
                declared.add(name)
            if labels:
                label_str = ",".join(f'{k}="{_escape_label(v)}"' for k, v in labels)
                lines.append(f"{name}{{{label_str}}} {value}")
            else:
                lines.append(f"{name} {value}")
        lines.append("")
        return "\n".join(lines)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


METRICS = MetricsRegistry()
