from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_permission import UserPermission


class UserPermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_dataset_ids(self, user_id: str) -> list[str]:
        result = await self._session.execute(
            select(UserPermission.dataset_id).where(UserPermission.user_id == user_id)
        )
        dataset_ids = list(result.scalars().all())
        return dataset_ids
