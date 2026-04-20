import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, agent_skill_table


async def get_by_uid(agent_uid: str, db: AsyncSession) -> Agent | None:
    stmt = select(Agent).where(
        Agent.agent_uid == agent_uid,
        Agent.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_by_owner(
    owner_uid: str, cursor: int | None, limit: int, db: AsyncSession
) -> list[Agent]:
    stmt = select(Agent).where(
        Agent.owner_uid == owner_uid,
        Agent.is_deleted == False,
    )
    if cursor is not None:
        stmt = stmt.where(Agent.pid > cursor)
    stmt = stmt.order_by(Agent.pid.asc()).limit(limit + 1)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_public(
    cursor: int | None, limit: int, db: AsyncSession
) -> list[Agent]:
    stmt = select(Agent).where(
        Agent.visibility == "public",
        Agent.is_deleted == False,
    )
    if cursor is not None:
        stmt = stmt.where(Agent.pid > cursor)
    stmt = stmt.order_by(Agent.pid.asc()).limit(limit + 1)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_visible_to_user(
    owner_uid: str, cursor: int | None, limit: int, db: AsyncSession
) -> list[Agent]:
    from sqlalchemy import or_
    stmt = select(Agent).where(
        Agent.is_deleted == False,
        or_(
            Agent.owner_uid == owner_uid,
            Agent.visibility == "public",
        ),
    )
    if cursor is not None:
        stmt = stmt.where(Agent.pid > cursor)
    stmt = stmt.order_by(Agent.pid.asc()).limit(limit + 1)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create(agent_data: dict, db: AsyncSession) -> Agent:
    agent = Agent(**agent_data)
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return agent


async def update(agent: Agent, update_data: dict, db: AsyncSession) -> Agent:
    for key, value in update_data.items():
        setattr(agent, key, value)
    await db.flush()
    await db.refresh(agent)
    return agent


async def soft_delete(agent: Agent, db: AsyncSession) -> None:
    agent.is_deleted = True
    await db.flush()


async def get_skill_uids(agent_uid: str, db: AsyncSession) -> list[str]:
    stmt = select(agent_skill_table.c.skill_uid).where(
        agent_skill_table.c.agent_uid == uuid.UUID(agent_uid)
    )
    result = await db.execute(stmt)
    return [str(row[0]) for row in result.fetchall()]


async def set_skill_uids(
    agent_uid: str, skill_uids: list[str], db: AsyncSession
) -> None:
    uid = uuid.UUID(agent_uid)
    await db.execute(
        delete(agent_skill_table).where(agent_skill_table.c.agent_uid == uid)
    )
    if skill_uids:
        for skill_uid in skill_uids:
            await db.execute(
                agent_skill_table.insert().values(
                    agent_uid=uid, skill_uid=uuid.UUID(skill_uid)
                )
            )
    await db.flush()
