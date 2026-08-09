from functools import lru_cache
from typing import Literal
from urllib.parse import quote, quote_plus

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RunMode = Literal["api", "worker", "all"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LlmProvider = Literal["openai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    enrichment_host: str = "0.0.0.0"
    enrichment_port: int = 8001
    log_level: LogLevel = "INFO"
    environment: str = "local"
    # Scraped on a dedicated port (not the public API). Disable via METRICS_ENABLED.
    metrics_enabled: bool = True
    metrics_host: str = "0.0.0.0"
    metrics_port: int = 9091
    # api = HTTP + publisher; worker = consumer only; all = both (local DX)
    run_mode: RunMode = "all"

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "autopulse"
    rabbitmq_password: str = "autopulse"
    rabbitmq_vhost: str = "/"
    rabbitmq_exchange: str = "autopulse.cars"
    rabbitmq_connection_name: str = "autopulse-enrichment"
    rabbitmq_heartbeat_sec: int = 30
    rabbitmq_connect_timeout_sec: float = 10.0
    rabbitmq_quorum_queues: bool = True
    rabbitmq_prefetch: int = 4

    routing_key_raw_created: str = "car.raw.created"
    routing_key_enriched_success: str = "car.enriched.success"
    routing_key_enrichment_failed: str = "car.enrichment.failed"
    routing_key_enrichment_dlq: str = "car.enrichment.dlq"
    routing_key_enrichment_retry: str = "car.enrichment.retry"
    enrichment_queue_name: str = "enrichment.raw"
    enrichment_dlq_name: str = "enrichment.dlq"
    enrichment_retry_queue_name: str = "enrichment.retry"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "autopulse"
    mongodb_collection_listings: str = "listings"
    mongodb_collection_inbox: str = "consumer_inbox"
    mongodb_collection_outbox: str = "publisher_outbox"

    llm_provider: LlmProvider = "openai"
    llm_model: str = "gpt-4o-mini"
    # Empty default keeps local heuristic path; use SecretStr so dumps hide the value.
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_sec: int = 30
    llm_max_retries: int = 3
    cv_max_workers: int = 4
    cv_watermark_enabled: bool = True
    cv_plate_enabled: bool = True
    # Default paths match Docker layout (PYTHONPATH=/app).
    cv_plate_onnx_path: str = "services/enrichment/models/plate_yolov8n.onnx"
    cv_plate_onnx_url: str = (
        "https://huggingface.co/joker5914/yolov8n-license-plate/"
        "resolve/main/best.onnx"
    )
    cv_plate_conf_threshold: float = 0.35
    cv_plate_iou_threshold: float = 0.45
    cv_watermark_onnx_path: str = "services/enrichment/models/scene_text_yolo11n.onnx"
    cv_watermark_onnx_url: str = (
        "https://huggingface.co/RyanBours/yolo11n-text/resolve/main/model.onnx"
    )
    cv_watermark_conf_threshold: float = 0.25
    cv_watermark_iou_threshold: float = 0.5
    enrichment_max_retries: int = 5
    enrichment_retry_base_delay_sec: float = 1.0
    enrichment_retry_max_delay_sec: float = 30.0
    outbox_drain_interval_sec: float = 5.0
    shutdown_timeout_sec: float = 10.0
    admin_ui_enabled: bool = True
    rabbitmq_management_url: str = "http://localhost:15672"
    pricer_base_url: str = "http://localhost:8002"
    pricer_admin_timeout_sec: float = 2.0
    # Pricer queue names (for Rabbit Management depth cards).
    pricer_queue_name: str = "pricer.enriched"
    pricer_dlq_name: str = "pricer.dlq"
    pricer_retry_queue_name: str = "pricer.retry"
    metrics_scrape_url: str = "http://localhost:9091/metrics"
    pricer_metrics_scrape_url: str = "http://localhost:9092/metrics"

    @property
    def rabbitmq_url(self) -> str:
        user = quote_plus(self.rabbitmq_user)
        password = quote_plus(self.rabbitmq_password)
        if self.rabbitmq_vhost in {"", "/"}:
            vhost = ""
        else:
            vhost = quote(self.rabbitmq_vhost, safe="")
        return (
            f"amqp://{user}:{password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/{vhost}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
