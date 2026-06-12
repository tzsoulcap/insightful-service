import logging

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.user_permission import UserPermissionRepository
from app.services.dify import DifyService
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


async def get_user_id(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    # 1. Legacy: X-User-Id header (kept for backward compat)
    user_id = request.headers.get(settings.USER_ID_HEADER)
    if user_id:
        return user_id

    # 2. JWT Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_access_token(token, settings)
        if payload:
            sub = payload.get("sub")
            if sub:
                return sub

    # 3. Dev fallback — log clearly so it's obvious in logs
    logger.warning("No auth found (no X-User-Id header, no valid JWT). Using fallback: guest")
    return "guest"


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
