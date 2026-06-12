import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.group import Group, GroupMember
from app.models.user import User
from app.repositories.group import GroupRepository
from app.repositories.user import UserRepository
from app.schemas.group import (
    AddGroupMembersRequest,
    GroupCreate,
    GroupDetailResponse,
    GroupListResponse,
    GroupMemberResponse,
    GroupResponse,
    GroupUpdate,
)

router = APIRouter(prefix="/groups", tags=["Groups"])


def _get_group_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> GroupRepository:
    return GroupRepository(session)


def _get_user_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> UserRepository:
    return UserRepository(session)


async def _get_group_or_404(group_id: uuid.UUID, repo: GroupRepository) -> Group:
    group = await repo.get_by_id(group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


# ── GET /groups ───────────────────────────────────────────────────────────────

@router.get("", response_model=GroupListResponse)
async def list_groups(
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[GroupRepository, Depends(_get_group_repo)],
    page: int = 1,
    limit: int = 20,
) -> GroupListResponse:
    clamped = max(1, min(limit, 100))
    groups, total = await repo.list_groups(page=page, limit=clamped)
    return GroupListResponse(
        data=groups,
        total=total,
        page=page,
        limit=clamped,
        has_more=(page * clamped) < total,
    )


# ── POST /groups ──────────────────────────────────────────────────────────────

@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[GroupRepository, Depends(_get_group_repo)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GroupResponse:
    existing = await repo.get_by_name(body.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Group name already exists"
        )
    group = Group(name=body.name, description=body.description)
    group = await repo.create(group)
    await session.commit()
    return GroupResponse.model_validate(group)


# ── GET /groups/{group_id} ────────────────────────────────────────────────────

@router.get("/{group_id}", response_model=GroupDetailResponse)
async def get_group(
    group_id: uuid.UUID,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[GroupRepository, Depends(_get_group_repo)],
) -> GroupDetailResponse:
    group = await _get_group_or_404(group_id, repo)
    return GroupDetailResponse.model_validate(group)


# ── PATCH /groups/{group_id} ──────────────────────────────────────────────────

@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: uuid.UUID,
    body: GroupUpdate,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[GroupRepository, Depends(_get_group_repo)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GroupResponse:
    group = await _get_group_or_404(group_id, repo)
    if body.name is not None and body.name != group.name:
        existing = await repo.get_by_name(body.name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Group name already exists"
            )
        group.name = body.name
    if body.description is not None:
        group.description = body.description
    await session.commit()
    await session.refresh(group)
    return GroupResponse.model_validate(group)


# ── DELETE /groups/{group_id} ─────────────────────────────────────────────────

@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[GroupRepository, Depends(_get_group_repo)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    group = await _get_group_or_404(group_id, repo)
    await repo.delete(group)
    await session.commit()


# ── GET /groups/{group_id}/members ────────────────────────────────────────────

@router.get("/{group_id}/members", response_model=list[GroupMemberResponse])
async def list_group_members(
    group_id: uuid.UUID,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[GroupRepository, Depends(_get_group_repo)],
) -> list[GroupMemberResponse]:
    group = await _get_group_or_404(group_id, repo)
    return [GroupMemberResponse.model_validate(m) for m in group.members]


# ── POST /groups/{group_id}/members ──────────────────────────────────────────

@router.post(
    "/{group_id}/members",
    response_model=list[GroupMemberResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_group_members(
    group_id: uuid.UUID,
    body: AddGroupMembersRequest,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[GroupRepository, Depends(_get_group_repo)],
    user_repo: Annotated[UserRepository, Depends(_get_user_repo)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[GroupMemberResponse]:
    await _get_group_or_404(group_id, repo)
    added: list[GroupMember] = []
    for user_id in body.user_ids:
        # Validate user exists
        user = await user_repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' not found",
            )
        # Skip if already member
        existing = await repo.get_member(group_id, user_id)
        if existing is not None:
            continue
        member = GroupMember(group_id=group_id, user_id=user_id)
        member = await repo.add_member(member)
        added.append(member)
    await session.commit()
    return [GroupMemberResponse.model_validate(m) for m in added]


# ── DELETE /groups/{group_id}/members/{user_id} ───────────────────────────────

@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[GroupRepository, Depends(_get_group_repo)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_group_or_404(group_id, repo)
    member = await repo.get_member(group_id, user_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    await repo.remove_member(member)
    await session.commit()
