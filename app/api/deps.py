from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.user import User
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.user_permission import UserPermissionRepository
from app.services.dify import DifyService
from app.services.retrieval_service import RetrievalService


async def get_user_id(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    user_id = request.headers.get(settings.USER_ID_HEADER)
    if user_id is None:
        user_id = "admin"
        print(f"Not Found \"X-User-Id\" header. Using default user: {user_id}")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing required header: {settings.USER_ID_HEADER}",
        )
    return user_id


def get_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserPermissionRepository:
    return UserPermissionRepository(session)


def get_dify_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DifyService:
    return DifyService(settings)


def get_retrieval_service(
    dify_service: Annotated[DifyService, Depends(get_dify_service)],
) -> RetrievalService:
    return RetrievalService(dify_service)


def get_knowledge_base_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeBaseRepository:
    return KnowledgeBaseRepository(session)


# ── Role guards ───────────────────────────────────────────────────────────────

_ADMIN_ROLES = {"admin", "super_admin"}


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


async def require_super_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin role required",
        )
    return current_user
