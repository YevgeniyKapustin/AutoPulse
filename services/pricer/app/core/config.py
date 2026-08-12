from functools import lru_cache
from typing import Literal, Self
from urllib.parse import quote, quote_plus

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from autopulse_shared.secrets_policy import (
    is_local_environment,
    require_strong_secret,
)

RunMode = Literal["api", "worker", "all"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
PricingEngineName = Literal["rules", "sklearn"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pricer_host: str = "0.0.0.0"
    pricer_port: int = 8002
    log_level: LogLevel = "INFO"
    environment: str = "local"
    # Scraped on a dedicated port (not the public API).
    # Disable via METRICS_ENABLED.
    metrics_enabled: bool = True
    metrics_host: str = "0.0.0.0"
    metrics_port: int = 9092
    # api = HTTP only; worker = consumer only;
    # all = both (local DX).
    run_mode: RunMode = "all"

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "autopulse"
    rabbitmq_password: str = "autopulse"
    rabbitmq_vhost: str = "/"
    rabbitmq_exchange: str = "autopulse.cars"
    rabbitmq_connection_name: str = "autopulse-pricer"
    rabbitmq_heartbeat_sec: int = 30
    rabbitmq_connect_timeout_sec: float = 10.0
    rabbitmq_quorum_queues: bool = True
    rabbitmq_prefetch: int = 8
    routing_key_enriched_success: str = "car.enriched.success"
    routing_key_priced_success: str = "car.priced.success"
    routing_key_pricer_dlq: str = "car.pricer.dlq"
    routing_key_pricer_retry: str = "car.pricer.retry"
    pricer_queue_name: str = "pricer.enriched"
    pricer_dlq_name: str = "pricer.dlq"
    pricer_retry_queue_name: str = "pricer.retry"
    pricer_max_retries: int = 5
    pricer_retry_base_delay_sec: float = 1.0
    pricer_retry_max_delay_sec: float = 30.0
    outbox_drain_interval_sec: float = 5.0
    shutdown_timeout_sec: float = 10.0
    # Empty password disables the gate (local DX).
    # When set: HTTP Basic + X-API-Key.
    ui_auth_username: str = "autopulse"
    ui_auth_password: SecretStr = SecretStr("")

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "autopulse"
    mysql_password: str = "autopulse"
    mysql_database: str = "autopulse_pricing"
    auto_create_tables: bool = False

    default_target_margin_pct: float = 12.0
    default_turnover_days: int = 21
    pricing_engine: PricingEngineName = "rules"

    @model_validator(mode="after")
    def reject_weak_secrets_outside_local(self) -> Self:
        if is_local_environment(self.environment):
            return self
        require_strong_secret("RABBITMQ_PASSWORD", self.rabbitmq_password)
        require_strong_secret("MYSQL_PASSWORD", self.mysql_password)
        ui_password = self.ui_auth_password.get_secret_value()
        if ui_password:
            require_strong_secret("UI_AUTH_PASSWORD", ui_password)
        return self

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

    @property
    def mysql_dsn(self) -> str:
        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+aiomysql://{user}:{password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def mysql_sync_dsn(self) -> str:
        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
