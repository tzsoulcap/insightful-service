import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User


async def get_user_by_username(
    session: AsyncSession, username: str, user_type: str = "local"
) -> User | None:
    result = await session.execute(
        select(User).where(User.username == username, User.user_type == user_type)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str | uuid.UUID) -> User | None:
    try:
        uid = uuid.UUID(str(user_id))
    except ValueError:
        return None
    result = await session.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()


_SORT_FIELDS: dict[str, object] = {
    "username": User.username,
    "role": User.role,
    "created_at": User.created_at,
}


async def get_all_users(
    session: AsyncSession,
    page: int = 1,
    limit: int = 20,
    keyword: str | None = None,
    role: str | None = None,
    sort: str = "created_at:asc",
) -> tuple[list[User], int]:
    from sqlalchemy import asc, desc, func

    # Parse sort parameter (e.g. "username:asc", "created_at:desc")
    sort_col = User.created_at
    sort_dir = asc
    if ":" in sort:
        field, direction = sort.split(":", 1)
        if field in _SORT_FIELDS:
            sort_col = _SORT_FIELDS[field]
        if direction.lower() == "desc":
            sort_dir = desc

    # Build WHERE conditions
    conditions = []
    if keyword:
        conditions.append(User.username.ilike(f"%{keyword}%"))
    if role:
        conditions.append(User.role == role)

    # Total count
    count_q = select(func.count()).select_from(User)
    if conditions:
        count_q = count_q.where(*conditions)
    total: int = (await session.execute(count_q)).scalar_one()

    # Paginated data
    data_q = select(User)
    if conditions:
        data_q = data_q.where(*conditions)
    data_q = data_q.order_by(sort_dir(sort_col)).offset((page - 1) * limit).limit(limit)
    users = list((await session.execute(data_q)).scalars().all())

    return users, total


async def create_user(
    session: AsyncSession,
    username: str,
    password: str,
    role: str = "user",
    user_type: str = "local",
) -> User:
    user = User(
        username=username,
        user_type=user_type,
        hashed_password=hash_password(password) if password else None,
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_role(session: AsyncSession, user: User, role: str) -> User:
    user.role = role
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_password(session: AsyncSession, user: User, new_password: str) -> None:
    user.hashed_password = hash_password(new_password)
    await session.commit()


async def delete_user(session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.commit()


async def authenticate_user(
    session: AsyncSession, username: str, password: str
) -> User | None:
    user = await get_user_by_username(session, username)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
