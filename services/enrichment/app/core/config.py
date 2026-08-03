from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    enrichment_host: str = "0.0.0.0"
    enrichment_port: int = 8001
    log_level: str = "INFO"

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "autopulse"
    rabbitmq_password: str = "autopulse"
    rabbitmq_vhost: str = "/"
    rabbitmq_exchange: str = "autopulse.cars"

    routing_key_raw_created: str = "car.raw.created"
    routing_key_enriched_success: str = "car.enriched.success"
    routing_key_enrichment_failed: str = "car.enrichment.failed"
    routing_key_enrichment_dlq: str = "car.enrichment.dlq"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "autopulse"
    mongodb_collection_listings: str = "listings"

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_timeout_sec: int = 30
    llm_max_retries: int = 3
    cv_max_workers: int = 4
    enrichment_max_retries: int = 5

    @property
    def rabbitmq_url(self) -> str:
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
