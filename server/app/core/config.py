from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ragsearch:ragsearch@localhost:5433/ragsearch"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-nano"
    openai_embeddings_api_key: str = ""
    openai_embeddings_model: str = "text-embedding-3-small"
    run_migrations: bool = True

    @property
    def openai_available(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()
