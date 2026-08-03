from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    enrichment_host: str = "0.0.0.0"
    enrichment_port: int = 8001
    log_level: str = "INFO"
    environment: str = "local"
    # api = HTTP + publisher; worker = consumer only; all = both (local DX)
    run_mode: Literal["api", "worker", "all"] = "all"

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
    enrichment_queue_name: str = "enrichment.raw"
    enrichment_dlq_name: str = "enrichment.dlq"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "autopulse"
    mongodb_collection_listings: str = "listings"
    mongodb_collection_inbox: str = "consumer_inbox"
    mongodb_collection_outbox: str = "publisher_outbox"

    llm_provider: str = "openai"
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
