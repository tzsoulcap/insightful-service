from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

_dify_db_url = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

dify_engine = create_async_engine(_dify_db_url, echo=False, pool_pre_ping=True)
dify_async_session = async_sessionmaker(
    dify_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_dify_db() -> AsyncGenerator[AsyncSession, None]:
    async with dify_async_session() as session:
        yield session
