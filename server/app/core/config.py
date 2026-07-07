import os

from pydantic_settings import BaseSettings, SettingsConfigDict


_env_file = ".env" if os.path.isfile(".env") else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file, extra="ignore")

    database_url: str = "postgresql+asyncpg://ragsearch:ragsearch@localhost:5433/ragsearch"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-nano"
    openai_embeddings_api_key: str = ""
    openai_embeddings_model: str = "text-embedding-3-small"


settings = Settings()
