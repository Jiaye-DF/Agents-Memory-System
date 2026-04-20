from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_language import AgentLanguage


async def list_active(db: AsyncSession) -> list[AgentLanguage]:
    stmt = (
        select(AgentLanguage)
        .where(
            AgentLanguage.is_active == True,
            AgentLanguage.is_deleted == False,
        )
        .order_by(AgentLanguage.sort_order.asc(), AgentLanguage.pid.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_all(
    cursor: int | None, limit: int, db: AsyncSession
) -> list[AgentLanguage]:
    stmt = select(AgentLanguage).where(AgentLanguage.is_deleted == False)
    if cursor is not None:
        stmt = stmt.where(AgentLanguage.pid > cursor)
    stmt = stmt.order_by(
        AgentLanguage.sort_order.asc(), AgentLanguage.pid.asc()
    ).limit(limit + 1)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_uid(uid: str, db: AsyncSession) -> AgentLanguage | None:
    stmt = select(AgentLanguage).where(
        AgentLanguage.agent_language_uid == uid,
        AgentLanguage.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_code(code: str, db: AsyncSession) -> AgentLanguage | None:
    stmt = select(AgentLanguage).where(
        AgentLanguage.code == code,
        AgentLanguage.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_by_code(
    code: str, db: AsyncSession
) -> AgentLanguage | None:
    stmt = select(AgentLanguage).where(
        AgentLanguage.code == code,
        AgentLanguage.is_active == True,
        AgentLanguage.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_default(db: AsyncSession) -> AgentLanguage | None:
    stmt = select(AgentLanguage).where(
        AgentLanguage.is_default == True,
        AgentLanguage.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def clear_default(db: AsyncSession, except_pid: int | None = None) -> None:
    """將所有其他語言的 is_default 設為 FALSE（在同一 transaction 切換預設時使用）"""
    stmt = update(AgentLanguage).where(
        AgentLanguage.is_default == True,
        AgentLanguage.is_deleted == False,
    )
    if except_pid is not None:
        stmt = stmt.where(AgentLanguage.pid != except_pid)
    stmt = stmt.values(is_default=False)
    await db.execute(stmt)
    await db.flush()


async def create(data: dict, db: AsyncSession) -> AgentLanguage:
    obj = AgentLanguage(**data)
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return obj


async def update_obj(
    obj: AgentLanguage, update_data: dict, db: AsyncSession
) -> AgentLanguage:
    for key, value in update_data.items():
        setattr(obj, key, value)
    await db.flush()
    await db.refresh(obj)
    return obj


async def soft_delete(obj: AgentLanguage, db: AsyncSession) -> None:
    obj.is_deleted = True
    await db.flush()
