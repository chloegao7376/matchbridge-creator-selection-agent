from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Creator Selection Agent"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://creator_agent:creator_agent@localhost:5432/creator_agent"
    sql_echo: bool = False
    embedding_provider: str = "hashing"
    embedding_model: str = "local_hashing_char_ngram_v1"
    embedding_dimension: int = 1536

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
