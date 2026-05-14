from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.citation import router as citation_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.image_proxy import router as image_proxy_router
from app.api.v1.knowledge_bases import router as knowledge_bases_router
from app.api.v1.pdf_pipeline import router as pdf_pipeline_router
from app.api.v1.version import router as version_router
from app.api.v1.weaviate import router as weaviate_router
from app.core.config import get_settings
from app.core.database import Base, engine
import app.models.user  # noqa: F401  — register User table with Base metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (development convenience)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanly close DB connections on shutdown
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title="Insightful Service",
    description="Middleware between Frontend and Dify.ai",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

api_prefix = "/v1"

app.include_router(auth_router, prefix=api_prefix)
app.include_router(chat_router, prefix=api_prefix)
app.include_router(citation_router)
app.include_router(conversations_router, prefix=api_prefix)
app.include_router(image_proxy_router, prefix=api_prefix)
app.include_router(knowledge_bases_router, prefix=api_prefix)
app.include_router(pdf_pipeline_router, prefix=api_prefix)
app.include_router(version_router, prefix=api_prefix)
app.include_router(weaviate_router, prefix=api_prefix)



@app.get("/health")
async def health():
    return {"status": "ok"}
