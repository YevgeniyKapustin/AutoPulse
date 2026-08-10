"""Classify RabbitMQ queue depths for ops alert cards."""

from __future__ import annotations

from typing import Literal

QueueAlertLevel = Literal["ok", "warn", "bad", "unknown"]
QueueKind = Literal["work", "retry", "dlq"]


def classify_depth(
    depth: int | None,
    *,
    kind: QueueKind,
    work_warn_depth: int,
    dlq_warn_depth: int,
) -> QueueAlertLevel:
    """Map a depth to a card level for the ops dashboard."""
    if depth is None:
        return "unknown"
    if kind == "dlq":
        return "bad" if depth > dlq_warn_depth else "ok"
    # Work + retry share one backlog threshold.
    if depth > work_warn_depth:
        return "bad"
    if work_warn_depth > 0 and depth > max(work_warn_depth // 2, 0):
        return "warn"
    return "ok"
