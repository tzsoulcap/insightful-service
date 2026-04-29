from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.repositories.user_permission import UserPermissionRepository
from app.services.dify import DifyService


async def get_user_id(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    # Read from the dynamically configured header name (default: X-User-Id)
    # print(request.headers)
    user_id = request.headers.get(settings.USER_ID_HEADER)
    if user_id is None:
        user_id = "admin"
        print(f"Not Found \"X-User-Id\" header. Using default user: {user_id}")
    # print(f"Extracted user_id from header {settings.USER_ID_HEADER}: {user_id}")
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
