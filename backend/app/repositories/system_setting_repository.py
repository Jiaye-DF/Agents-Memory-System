from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting


async def list_public(db: AsyncSession) -> list[SystemSetting]:
    stmt = (
        select(SystemSetting)
        .where(
            SystemSetting.is_public == True,
            SystemSetting.is_active == True,
            SystemSetting.is_deleted == False,
        )
        .order_by(SystemSetting.pid.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_all(db: AsyncSession) -> list[SystemSetting]:
    stmt = (
        select(SystemSetting)
        .where(SystemSetting.is_deleted == False)
        .order_by(SystemSetting.pid.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_key(key: str, db: AsyncSession) -> SystemSetting | None:
    stmt = select(SystemSetting).where(
        SystemSetting.key == key,
        SystemSetting.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_by_key(
    key: str, db: AsyncSession
) -> SystemSetting | None:
    stmt = select(SystemSetting).where(
        SystemSetting.key == key,
        SystemSetting.is_active == True,
        SystemSetting.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_obj(
    obj: SystemSetting, update_data: dict, db: AsyncSession
) -> SystemSetting:
    for key, value in update_data.items():
        setattr(obj, key, value)
    await db.flush()
    await db.refresh(obj)
    return obj
