from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.app_knowledge_bases import router as app_knowledge_bases_router
from app.api.v1.auth import router as auth_router
from app.api.v1.batch import router as batch_router
from app.api.v1.chat import router as chat_router
from app.api.v1.citation import router as citation_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.docker_mgmt import router as docker_router
from app.api.v1.dify_storage import router as dify_storage_router
from app.api.v1.groups import router as groups_router
from app.api.v1.image_proxy import router as image_proxy_router
from app.api.v1.knowledge_bases import router as knowledge_bases_router
from app.api.v1.pdf_pipeline import router as pdf_pipeline_router
from app.api.v1.users import router as users_router
from app.api.v1.version import router as version_router
from app.api.v1.weaviate import router as weaviate_router
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.scheduler import recover_pending_batches, scheduler
import app.models  # noqa: F401  — register all ORM models with Base metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (development convenience)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Start scheduler and recover pending batches
    scheduler.start()
    await recover_pending_batches()
    yield
    # Shutdown scheduler and close DB connections
    scheduler.shutdown(wait=False)
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title="Insightful Service",
    description="Middleware between Frontend and Dify.ai",
    version="0.2.0",
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
app.include_router(app_knowledge_bases_router, prefix=api_prefix)
app.include_router(batch_router, prefix=api_prefix)
app.include_router(chat_router, prefix=api_prefix)
app.include_router(citation_router, prefix=api_prefix)
app.include_router(conversations_router, prefix=api_prefix)
app.include_router(docker_router, prefix=api_prefix)
app.include_router(dify_storage_router, prefix=api_prefix)
app.include_router(groups_router, prefix=api_prefix)
app.include_router(image_proxy_router, prefix=api_prefix)
app.include_router(knowledge_bases_router, prefix=api_prefix)
app.include_router(pdf_pipeline_router, prefix=api_prefix)
app.include_router(users_router, prefix=api_prefix)
app.include_router(version_router, prefix=api_prefix)
app.include_router(weaviate_router, prefix=api_prefix)


@app.get("/health")
async def health():
    return {"status": "ok"}



# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Create tables on startup (development convenience)
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#     # Start scheduler and recover pending batches
#     scheduler.start()
#     await recover_pending_batches()
#     yield
#     # Shutdown scheduler and close DB connections
#     scheduler.shutdown(wait=False)
#     await engine.dispose()


# settings = get_settings()

# app = FastAPI(
#     title="Insightful Service",
#     description="Middleware between Frontend and Dify.ai",
#     version="0.1.0",
#     lifespan=lifespan,
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.CORS_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
#     expose_headers=["*"]
# )

# api_prefix = "/v1"

# app.include_router(auth_router, prefix=api_prefix)
# app.include_router(batch_router, prefix=api_prefix)
# app.include_router(chat_router, prefix=api_prefix)
# app.include_router(citation_router, prefix=api_prefix)
# app.include_router(conversations_router, prefix=api_prefix)
# app.include_router(docker_router, prefix=api_prefix)
# app.include_router(dify_storage_router, prefix=api_prefix)
# app.include_router(image_proxy_router, prefix=api_prefix)
# app.include_router(knowledge_bases_router, prefix=api_prefix)
# app.include_router(pdf_pipeline_router, prefix=api_prefix)
# app.include_router(users_router, prefix=api_prefix)
# app.include_router(version_router, prefix=api_prefix)
# app.include_router(weaviate_router, prefix=api_prefix)



# @app.get("/health")
# async def health():
#     return {"status": "ok"}
