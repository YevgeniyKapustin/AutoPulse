CREATE DATABASE IF NOT EXISTS logs;

CREATE TABLE IF NOT EXISTS logs.python_app_logs
(
    timestamp DateTime64(3, 'UTC') DEFAULT now64(3),
    level LowCardinality(String),
    service LowCardinality(String),
    environment LowCardinality(String),
    event String,
    trace_id String,
    user_id Nullable(Int64),
    attributes Map(String, String),
    raw String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (service, level, timestamp, trace_id)
TTL toDateTime(timestamp) + INTERVAL 30 DAY;
