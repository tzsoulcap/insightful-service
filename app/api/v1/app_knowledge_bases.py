import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.knowledge_base import KnowledgeBase, KnowledgePermission
from app.models.user import User
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.knowledge_base import (
    AllowedKnowledgeBase,
    AppKnowledgeBaseCreate,
    AppKnowledgeBaseListResponse,
    AppKnowledgeBaseResponse,
    PermissionCreate,
    PermissionResponse,
)

router = APIRouter(prefix="/app/knowledge-bases", tags=["App Knowledge Bases"])


def _get_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> KnowledgeBaseRepository:
    return KnowledgeBaseRepository(session)


async def _get_kb_or_404(kb_id: uuid.UUID, repo: KnowledgeBaseRepository) -> KnowledgeBase:
    kb = await repo.get_by_id(kb_id)
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


# ── GET /app/knowledge-bases ──────────────────────────────────────────────────

@router.get("", response_model=AppKnowledgeBaseListResponse)
async def list_app_knowledge_bases(
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[KnowledgeBaseRepository, Depends(_get_repo)],
    page: int = 1,
    limit: int = 20,
) -> AppKnowledgeBaseListResponse:
    clamped = max(1, min(limit, 100))
    items, total = await repo.list_knowledge_bases(page=page, limit=clamped)
    return AppKnowledgeBaseListResponse(
        data=items,
        total=total,
        page=page,
        limit=clamped,
        has_more=(page * clamped) < total,
    )


# ── POST /app/knowledge-bases ─────────────────────────────────────────────────

@router.post("", response_model=AppKnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_app_knowledge_base(
    body: AppKnowledgeBaseCreate,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[KnowledgeBaseRepository, Depends(_get_repo)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AppKnowledgeBaseResponse:
    existing = await repo.get_by_dify_dataset_id(body.dify_dataset_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Knowledge base with this dify_dataset_id already exists",
        )
    kb = KnowledgeBase(
        dify_dataset_id=body.dify_dataset_id,
        dify_dataset_name=body.dify_dataset_name,
    )
    kb = await repo.create(kb)
    await session.commit()
    await session.refresh(kb)
    return AppKnowledgeBaseResponse.model_validate(kb)


# ── GET /app/knowledge-bases/{kb_id} ─────────────────────────────────────────

@router.get("/{kb_id}", response_model=AppKnowledgeBaseResponse)
async def get_app_knowledge_base(
    kb_id: uuid.UUID,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[KnowledgeBaseRepository, Depends(_get_repo)],
) -> AppKnowledgeBaseResponse:
    kb = await _get_kb_or_404(kb_id, repo)
    return AppKnowledgeBaseResponse.model_validate(kb)


# ── DELETE /app/knowledge-bases/{kb_id} ──────────────────────────────────────

@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app_knowledge_base(
    kb_id: uuid.UUID,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[KnowledgeBaseRepository, Depends(_get_repo)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    kb = await _get_kb_or_404(kb_id, repo)
    await repo.delete(kb)
    await session.commit()


# ── GET /app/knowledge-bases/{kb_id}/permissions ─────────────────────────────

@router.get("/{kb_id}/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    kb_id: uuid.UUID,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[KnowledgeBaseRepository, Depends(_get_repo)],
) -> list[PermissionResponse]:
    await _get_kb_or_404(kb_id, repo)
    perms = await repo.list_permissions(kb_id)
    return [PermissionResponse.model_validate(p) for p in perms]


# ── POST /app/knowledge-bases/{kb_id}/permissions ────────────────────────────

@router.post(
    "/{kb_id}/permissions",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_permission(
    kb_id: uuid.UUID,
    body: PermissionCreate,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[KnowledgeBaseRepository, Depends(_get_repo)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PermissionResponse:
    # Validate: must have exactly one of group_id or user_id
    if (body.group_id is None) == (body.user_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Exactly one of group_id or user_id must be provided",
        )
    await _get_kb_or_404(kb_id, repo)
    perm = KnowledgePermission(
        knowledge_id=kb_id,
        group_id=body.group_id,
        user_id=body.user_id,
        permission_level=body.permission_level,
    )
    try:
        perm = await repo.add_permission(perm)
        await session.commit()
        await session.refresh(perm)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission for this group or user already exists on this knowledge base",
        )
    return PermissionResponse.model_validate(perm)


# ── DELETE /app/knowledge-bases/permissions/{permission_id} ──────────────────

@router.delete("/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
    permission_id: uuid.UUID,
    _: Annotated[User, Depends(require_admin)],
    repo: Annotated[KnowledgeBaseRepository, Depends(_get_repo)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    perm = await repo.get_permission(permission_id)
    if perm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
        )
    await repo.delete_permission(perm)
    await session.commit()


# ── GET /app/me/knowledge-bases ── (allowed KBs for current user) ─────────────

@router.get("/me/allowed", response_model=list[AllowedKnowledgeBase], tags=["Me"])
async def list_my_allowed_knowledge_bases(
    current_user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[KnowledgeBaseRepository, Depends(_get_repo)],
) -> list[AllowedKnowledgeBase]:
    rows = await repo.get_allowed_knowledge_bases(current_user.id)
    return [
        AllowedKnowledgeBase(
            knowledge_id=knowledge_id,
            dify_dataset_id=dify_dataset_id,
            dify_dataset_name=dify_dataset_name,
        )
        for knowledge_id, dify_dataset_id, dify_dataset_name in rows
    ]
