import uuid
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import Select, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, agent_skill_table


async def get_by_uid(agent_uid: str, db: AsyncSession) -> Agent | None:
    stmt = select(Agent).where(
        Agent.agent_uid == agent_uid,
        Agent.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def stmt_visible_to_user(owner_uid: str) -> Select[tuple[Agent]]:
    return select(Agent).where(
        Agent.is_deleted == False,
        or_(
            Agent.owner_uid == owner_uid,
            Agent.visibility == "public",
        ),
    )


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


async def get_skill_uids_map(
    agent_uids: Iterable[str], db: AsyncSession
) -> dict[str, list[str]]:
    """批次取得多個 agent 的 skill_uids，避免列表查詢時逐項 N+1。"""
    uids = [uuid.UUID(a) for a in agent_uids]
    result: dict[str, list[str]] = defaultdict(list)
    if not uids:
        return result

    stmt = select(
        agent_skill_table.c.agent_uid, agent_skill_table.c.skill_uid
    ).where(agent_skill_table.c.agent_uid.in_(uids))
    rows = await db.execute(stmt)
    for agent_uid, skill_uid in rows.fetchall():
        result[str(agent_uid)].append(str(skill_uid))
    return result


async def list_by_skill_uid(
    skill_uid: str, db: AsyncSession
) -> list[Agent]:
    """列出引用指定 skill 的未刪除 agents（owner relationship 一併載入）。"""
    stmt = (
        select(Agent)
        .join(
            agent_skill_table,
            agent_skill_table.c.agent_uid == Agent.agent_uid,
        )
        .where(
            agent_skill_table.c.skill_uid == uuid.UUID(skill_uid),
            Agent.is_deleted == False,
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def set_skill_uids(
    agent_uid: str, skill_uids: list[str], db: AsyncSession
) -> None:
    uid = uuid.UUID(agent_uid)
    await db.execute(
        delete(agent_skill_table).where(agent_skill_table.c.agent_uid == uid)
    )
    if skill_uids:
        await db.execute(
            agent_skill_table.insert(),
            [
                {"agent_uid": uid, "skill_uid": uuid.UUID(s)}
                for s in skill_uids
            ],
        )
    await db.flush()
