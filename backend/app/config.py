from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    crustdata_api_key: str = ""
    crustdata_base_url: str = "https://api.crustdata.com/screener/company"
    database_url: str = "postgresql+asyncpg://grc:grc@localhost:5432/grc"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic: str = "risk_signals"
    model_version: str = "v1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

