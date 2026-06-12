from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database (App's own PostgreSQL — not Dify's Postgres)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/insightful"

    # LDAP
    LDAP_SERVER_IP: str = ""
    LDAP_DOMAIN: str = "attg.co.th"

    # Dify Postgres Connection (if using Dify's Postgres for data storage, otherwise not needed)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "difyai123456"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "dify"
    DIFY_STORAGE_PATH: str = "D:\\llm_dev\\dify\\docker\\volumes\\app\\storage"

    # Dify Weaviate Connection
    DIFY_WEAVIATE_KEY: str = "weaviate_key_placeholder"
    DIFY_WEAVIATE_HOST: str = "http://localhost"
    DIFY_WEAVIATE_PORT: int = 8080
    DIFY_WEAVIATE_GRPC_PORT: int = 50051

    # Dify
    DIFY_BASE_URL: str = "https://api.dify.ai/v1"
    DIFY_API_KEY: str = ""
    DIFY_KNOWLEDGE_API_KEY: str = ""

    # Misspell Correction API
    MISSPELL_API_KEY: str = ""
    MISSPELL_BASE_URL: str = "http://localhost/v1"

    # AD / Auth — configurable header name for user identification
    USER_ID_HEADER: str = "X-User-Id"

    # App version (bump manually on each release)
    APP_VERSION: str = "0.2.0"

    # JWT
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # PDF batch processing
    PDF_STORAGE_PATH: str = "./pdf_original"

    # OCR (Typhoon OCR)
    OCR_MODEL: str = "typhoon-ai/typhoon-ocr1.5-2b"
    OCR_BASE_URL: str = "http://localhost:8002/v1"
    OCR_API_KEY: str = "no-key"
    OCR_TARGET_IMAGE_DIM: int = 1500
    OCR_FIGURE_LANGUAGE: str = "Thai"
    OCR_TASK_TYPE: str = "v1.5"
    OCR_MAX_TOKENS_CAP: int = 8192


@lru_cache
def get_settings() -> Settings:
    return Settings()
