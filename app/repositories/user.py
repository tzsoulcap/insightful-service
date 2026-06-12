import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str, user_type: str = "local") -> User | None:
        result = await self._session.execute(
            select(User).where(User.username == username, User.user_type == user_type)
        )
        return result.scalar_one_or_none()

    async def list_users(
        self, *, page: int = 1, limit: int = 20, is_active: bool | None = None
    ) -> tuple[list[User], int]:
        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
            count_stmt = count_stmt.where(User.is_active == is_active)
        stmt = stmt.offset((page - 1) * limit).limit(limit)
        users = list((await self._session.execute(stmt)).scalars().all())
        total = (await self._session.execute(count_stmt)).scalar_one()
        return users, total

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def deactivate(self, user: User) -> None:
        user.is_active = False
        await self._session.flush()
