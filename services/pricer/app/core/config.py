from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pricer_host: str = "0.0.0.0"
    pricer_port: int = 8002
    log_level: str = "INFO"

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "autopulse"
    rabbitmq_password: str = "autopulse"
    rabbitmq_vhost: str = "/"
    rabbitmq_exchange: str = "autopulse.cars"
    routing_key_enriched_success: str = "car.enriched.success"
    routing_key_pricer_dlq: str = "car.pricer.dlq"
    pricer_queue_name: str = "pricer.enriched"
    pricer_dlq_name: str = "pricer.dlq"
    pricer_max_retries: int = 5

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "autopulse"
    mysql_password: str = "autopulse"
    mysql_database: str = "autopulse_pricing"
    auto_create_tables: bool = False

    default_target_margin_pct: float = 12.0
    default_turnover_days: int = 21
    pricing_engine: str = "rules"

    @property
    def rabbitmq_url(self) -> str:
        vhost = "" if self.rabbitmq_vhost in {"", "/"} else self.rabbitmq_vhost
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/{vhost}"
        )

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def mysql_sync_dsn(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
