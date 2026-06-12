import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group, GroupMember


class GroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, group_id: uuid.UUID) -> Group | None:
        result = await self._session.execute(select(Group).where(Group.id == group_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Group | None:
        result = await self._session.execute(select(Group).where(Group.name == name))
        return result.scalar_one_or_none()

    async def list_groups(self, *, page: int = 1, limit: int = 20) -> tuple[list[Group], int]:
        stmt = select(Group).offset((page - 1) * limit).limit(limit)
        count_stmt = select(func.count()).select_from(Group)
        groups = list((await self._session.execute(stmt)).scalars().all())
        total = (await self._session.execute(count_stmt)).scalar_one()
        return groups, total

    async def create(self, group: Group) -> Group:
        self._session.add(group)
        await self._session.flush()
        await self._session.refresh(group)
        return group

    async def delete(self, group: Group) -> None:
        await self._session.delete(group)
        await self._session.flush()

    # ── Members ───────────────────────────────────────────────────────────────

    async def get_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupMember | None:
        result = await self._session.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def add_member(self, member: GroupMember) -> GroupMember:
        self._session.add(member)
        await self._session.flush()
        return member

    async def remove_member(self, member: GroupMember) -> None:
        await self._session.delete(member)
        await self._session.flush()

    async def get_user_group_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self._session.execute(
            select(GroupMember.group_id).where(GroupMember.user_id == user_id)
        )
        return list(result.scalars().all())
