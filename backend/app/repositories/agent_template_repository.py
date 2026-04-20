from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_template import AgentTemplate


async def list_active(db: AsyncSession) -> list[AgentTemplate]:
    stmt = (
        select(AgentTemplate)
        .where(
            AgentTemplate.is_active == True,
            AgentTemplate.is_deleted == False,
        )
        .order_by(AgentTemplate.sort_order.asc(), AgentTemplate.pid.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def stmt_all() -> Select[tuple[AgentTemplate]]:
    return (
        select(AgentTemplate)
        .where(AgentTemplate.is_deleted == False)
        .order_by(AgentTemplate.sort_order.asc(), AgentTemplate.pid.asc())
    )


async def get_by_uid(uid: str, db: AsyncSession) -> AgentTemplate | None:
    stmt = select(AgentTemplate).where(
        AgentTemplate.agent_template_uid == uid,
        AgentTemplate.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_key(key: str, db: AsyncSession) -> AgentTemplate | None:
    stmt = select(AgentTemplate).where(
        AgentTemplate.template_key == key,
        AgentTemplate.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create(data: dict, db: AsyncSession) -> AgentTemplate:
    obj = AgentTemplate(**data)
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return obj


async def update_obj(
    obj: AgentTemplate, update_data: dict, db: AsyncSession
) -> AgentTemplate:
    for key, value in update_data.items():
        setattr(obj, key, value)
    await db.flush()
    await db.refresh(obj)
    return obj


async def soft_delete(obj: AgentTemplate, db: AsyncSession) -> None:
    obj.is_deleted = True
    await db.flush()
