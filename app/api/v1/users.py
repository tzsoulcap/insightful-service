from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import ResetPasswordRequest, UpdateRoleRequest, UserListResponse, UserResponse
from app.services.auth_service import (
    delete_user,
    get_all_users,
    get_user_by_id,
    update_user_password,
    update_user_role,
)

router = APIRouter(prefix="/users", tags=["Users"])


def _require_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


async def _get_target_user(user_id: str, session: AsyncSession) -> User:
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# ── GET /users ────────────────────────────────────────────────────────────────

@router.get("", response_model=UserListResponse)
async def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    role: str | None = None,
    sort: str = "created_at:asc",
) -> UserListResponse:
    _require_admin(current_user)
    clamped_limit = max(1, min(limit, 100))
    users, total = await get_all_users(
        session,
        page=page,
        limit=clamped_limit,
        keyword=keyword,
        role=role,
        sort=sort,
    )
    return UserListResponse(
        data=users,
        total=total,
        page=page,
        limit=clamped_limit,
        has_more=(page * clamped_limit) < total,
    )


# ── PATCH /users/{user_id}/role ───────────────────────────────────────────────

@router.patch("/{user_id}/role", response_model=UserResponse)
async def patch_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    _require_admin(current_user)
    target = await _get_target_user(user_id, session)
    return await update_user_role(session, target, body.role)


# ── PATCH /users/{user_id}/password ──────────────────────────────────────────

@router.patch("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def patch_user_password(
    user_id: str,
    body: ResetPasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    _require_admin(current_user)
    target = await _get_target_user(user_id, session)
    await update_user_password(session, target, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── DELETE /users/{user_id} ───────────────────────────────────────────────────

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_endpoint(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    _require_admin(current_user)
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    target = await _get_target_user(user_id, session)
    await delete_user(session, target)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
