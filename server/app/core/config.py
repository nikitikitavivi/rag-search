import os
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_env_file = ".env" if os.path.isfile(".env") else None


def _fix_asyncpg_url(url: str) -> str:
    """Convert a standard postgres:// URL into an asyncpg-compatible one."""
    parsed = urlparse(url)

    scheme = parsed.scheme
    if "+asyncpg" not in scheme:
        if scheme == "postgres":
            scheme = "postgresql+asyncpg"
        elif scheme == "postgresql":
            scheme = "postgresql+asyncpg"

    params = parse_qs(parsed.query)
    if "sslmode" in params:
        sslmode = params.pop("sslmode")[0]
        params["ssl"] = [sslmode]
    new_query = urlencode(params, doseq=True)

    return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file, extra="ignore")

    database_url: str = "postgresql+asyncpg://ragsearch:ragsearch@localhost:5433/ragsearch"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-nano"
    openai_embeddings_api_key: str = ""
    openai_embeddings_model: str = "text-embedding-3-small"

    @field_validator("database_url", mode="after")
    @classmethod
    def _ensure_asyncpg(cls, v: str) -> str:
        return _fix_asyncpg_url(v)


settings = Settings()
