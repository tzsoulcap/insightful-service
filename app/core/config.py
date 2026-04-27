from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./insightful.db"

    # Dify
    DIFY_BASE_URL: str = "https://api.dify.ai/v1"
    DIFY_API_KEY: str = ""

    # AD / Auth — configurable header name for user identification
    USER_ID_HEADER: str = "X-User-Id"

    # CORS
    CORS_ORIGINS: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
