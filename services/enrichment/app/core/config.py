from functools import lru_cache
from typing import Literal

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
    llm_api_key: str = ""
    llm_timeout_sec: int = 30
    llm_max_retries: int = 3
    cv_max_workers: int = 4
    enrichment_max_retries: int = 5
    enrichment_retry_base_delay_sec: float = 1.0
    enrichment_retry_max_delay_sec: float = 30.0
    shutdown_timeout_sec: float = 10.0

    @property
    def rabbitmq_url(self) -> str:
        vhost = "" if self.rabbitmq_vhost in {"", "/"} else self.rabbitmq_vhost
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/{vhost}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
