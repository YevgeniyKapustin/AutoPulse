"""AMQP / consumer string constants for enrichment messaging."""

from __future__ import annotations

HEADER_RETRY_COUNT = "retry_count"
CONTENT_TYPE_JSON = "application/json"
UNKNOWN_EXTERNAL_ID = "unknown"

METRIC_CONSUMER_ERRORS = "autopulse_consumer_errors_total"
METRIC_CONSUMER_ACK = "autopulse_consumer_ack_total"
METRIC_CONSUMER_DUPLICATES = "autopulse_consumer_duplicates_total"
METRIC_DLQ = "autopulse_dlq_total"
METRIC_RETRY_PUBLISHED = "autopulse_enrichment_retry_total"
