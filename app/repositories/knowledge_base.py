import uuid

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import GroupMember
from app.models.knowledge_base import KnowledgeBase, KnowledgePermission


class KnowledgeBaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, kb_id: uuid.UUID) -> KnowledgeBase | None:
        result = await self._session.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
        return result.scalar_one_or_none()

    async def get_by_dify_dataset_id(self, dify_dataset_id: str) -> KnowledgeBase | None:
        result = await self._session.execute(
            select(KnowledgeBase).where(KnowledgeBase.dify_dataset_id == dify_dataset_id)
        )
        return result.scalar_one_or_none()

    async def list_knowledge_bases(
        self, *, page: int = 1, limit: int = 20
    ) -> tuple[list[KnowledgeBase], int]:
        stmt = select(KnowledgeBase).offset((page - 1) * limit).limit(limit)
        count_stmt = select(func.count()).select_from(KnowledgeBase)
        items = list((await self._session.execute(stmt)).scalars().all())
        total = (await self._session.execute(count_stmt)).scalar_one()
        return items, total

    async def create(self, kb: KnowledgeBase) -> KnowledgeBase:
        self._session.add(kb)
        await self._session.flush()
        await self._session.refresh(kb)
        return kb

    async def delete(self, kb: KnowledgeBase) -> None:
        await self._session.delete(kb)
        await self._session.flush()

    # ── Permissions ───────────────────────────────────────────────────────────

    async def get_permission(self, permission_id: uuid.UUID) -> KnowledgePermission | None:
        result = await self._session.execute(
            select(KnowledgePermission).where(KnowledgePermission.id == permission_id)
        )
        return result.scalar_one_or_none()

    async def list_permissions(
        self, knowledge_id: uuid.UUID
    ) -> list[KnowledgePermission]:
        result = await self._session.execute(
            select(KnowledgePermission).where(KnowledgePermission.knowledge_id == knowledge_id)
        )
        return list(result.scalars().all())

    async def add_permission(self, perm: KnowledgePermission) -> KnowledgePermission:
        self._session.add(perm)
        await self._session.flush()
        await self._session.refresh(perm)
        return perm

    async def delete_permission(self, perm: KnowledgePermission) -> None:
        await self._session.delete(perm)
        await self._session.flush()

    # ── Permission query: get allowed datasets for a user ────────────────────

    async def get_allowed_knowledge_bases(
        self, user_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, str, str]]:
        """
        Returns list of (knowledge_id, dify_dataset_id, dify_dataset_name)
        for all knowledge bases the user has at least 'read' permission on,
        either directly or through a group membership.
        """
        stmt = (
            select(
                KnowledgeBase.id.label("knowledge_id"),
                KnowledgeBase.dify_dataset_id,
                KnowledgeBase.dify_dataset_name,
            )
            .join(KnowledgePermission, KnowledgePermission.knowledge_id == KnowledgeBase.id)
            .outerjoin(GroupMember, GroupMember.group_id == KnowledgePermission.group_id)
            .where(
                KnowledgePermission.permission_level.in_(["read", "write", "admin"]),
                or_(
                    KnowledgePermission.user_id == user_id,
                    GroupMember.user_id == user_id,
                ),
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return [(row.knowledge_id, row.dify_dataset_id, row.dify_dataset_name) for row in result]
