from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


async def get_by_uid(user_uid: str, db: AsyncSession) -> User | None:
    stmt = select(User).where(User.user_uid == user_uid, User.is_deleted == False)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_account(account: str, db: AsyncSession) -> User | None:
    stmt = select(User).where(User.account == account, User.is_deleted == False)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_account_and_username(
    account: str, username: str, db: AsyncSession
) -> User | None:
    stmt = select(User).where(
        User.account == account,
        User.username == username,
        User.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create(user_data: dict, db: AsyncSession) -> User:
    user = User(**user_data)
    db.add(user)
    await db.flush()
    return user


async def update(user: User, update_data: dict, db: AsyncSession) -> User:
    for key, value in update_data.items():
        setattr(user, key, value)
    await db.flush()
    await db.refresh(user)
    return user


async def list_users(cursor: int | None, limit: int, db: AsyncSession) -> list[User]:
    stmt = select(User).where(User.is_deleted == False)
    if cursor is not None:
        stmt = stmt.where(User.pid > cursor)
    stmt = stmt.order_by(User.pid.asc()).limit(limit + 1)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_role_by_name(name: str, db: AsyncSession) -> UserRole | None:
    stmt = select(UserRole).where(
        UserRole.name == name,
        UserRole.is_deleted == False,
        UserRole.is_active == True,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_role_by_uid(role_uid: str, db: AsyncSession) -> UserRole | None:
    stmt = select(UserRole).where(
        UserRole.user_role_uid == role_uid,
        UserRole.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_roles(db: AsyncSession) -> list[UserRole]:
    stmt = select(UserRole).where(
        UserRole.is_deleted == False
    ).order_by(UserRole.pid.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
