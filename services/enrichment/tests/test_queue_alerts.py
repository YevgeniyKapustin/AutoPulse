"""Queue depth classification for ops alerts."""

from services.enrichment.app.admin.queue_alerts import classify_depth


def test_dlq_any_message_is_bad_by_default() -> None:
    assert (
        classify_depth(0, kind="dlq", work_warn_depth=100, dlq_warn_depth=0) == "ok"
    )
    assert (
        classify_depth(1, kind="dlq", work_warn_depth=100, dlq_warn_depth=0) == "bad"
    )


def test_work_queue_warn_and_bad() -> None:
    assert (
        classify_depth(10, kind="work", work_warn_depth=100, dlq_warn_depth=0) == "ok"
    )
    assert (
        classify_depth(60, kind="work", work_warn_depth=100, dlq_warn_depth=0)
        == "warn"
    )
    assert (
        classify_depth(101, kind="work", work_warn_depth=100, dlq_warn_depth=0)
        == "bad"
    )


def test_missing_depth_unknown() -> None:
    assert (
        classify_depth(None, kind="retry", work_warn_depth=100, dlq_warn_depth=0)
        == "unknown"
    )
