import uuid
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, agent_skill_table
from app.models.skill import Skill


def _greatest_zero(expr):
    return func.greatest(expr, 0)


async def get_by_uid(agent_uid: str, db: AsyncSession) -> Agent | None:
    stmt = select(Agent).where(
        Agent.agent_uid == agent_uid,
        Agent.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_uids(
    agent_uids: list[str], db: AsyncSession, include_deleted: bool = False
) -> list[Agent]:
    """批次取得多個 agent（owner relationship 一併載入）。"""
    if not agent_uids:
        return []
    uuids = [uuid.UUID(u) for u in agent_uids]
    stmt = select(Agent).where(Agent.agent_uid.in_(uuids))
    if not include_deleted:
        stmt = stmt.where(Agent.is_deleted == False)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


def stmt_visible_to_user(user_uid: str) -> Select[tuple[Agent]]:
    return select(Agent).where(
        Agent.is_deleted == False,
        or_(
            Agent.owner_user_uid == user_uid,
            Agent.visibility == "public",
        ),
    )


ALLOWED_ORDER_FIELDS = {
    "favorite_count": Agent.favorite_count,
    "download_count": Agent.download_count,
    "created_at": Agent.created_at,
    "updated_at": Agent.updated_at,
}


def get_order_column(order_by: str | None):
    """白名單驗證後回傳 SQLAlchemy 欄位；未指定時預設 `created_at`。"""
    key = order_by or "created_at"
    if key not in ALLOWED_ORDER_FIELDS:
        raise ValueError(f"不支援的 order_by：{order_by}")
    return ALLOWED_ORDER_FIELDS[key]


async def create(agent_data: dict, db: AsyncSession) -> Agent:
    agent = Agent(**agent_data)
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return agent


async def update_obj(agent: Agent, update_data: dict, db: AsyncSession) -> Agent:
    for key, value in update_data.items():
        setattr(agent, key, value)
    await db.flush()
    await db.refresh(agent)
    return agent


async def soft_delete(agent: Agent, db: AsyncSession) -> None:
    agent.is_deleted = True
    await db.flush()


async def increment_favorite_count(
    agent_uid: str, delta: int, db: AsyncSession
) -> int | None:
    """原子遞增 `favorite_count`；下限為 0（避免 race 變負）。

    回傳更新後的 favorite_count；若找不到 agent 或已軟刪回傳 None。
    """
    stmt = (
        update(Agent)
        .where(
            Agent.agent_uid == uuid.UUID(agent_uid),
            Agent.is_deleted == False,  # noqa: E712
        )
        .values(
            favorite_count=_greatest_zero(Agent.favorite_count + delta)
        )
        .returning(Agent.favorite_count)
    )
    result = await db.execute(stmt)
    row = result.first()
    return int(row[0]) if row else None


async def increment_download_count(
    agent_uid: str, delta: int, db: AsyncSession
) -> int | None:
    stmt = (
        update(Agent)
        .where(
            Agent.agent_uid == uuid.UUID(agent_uid),
            Agent.is_deleted == False,  # noqa: E712
        )
        .values(download_count=Agent.download_count + delta)
        .returning(Agent.download_count)
    )
    result = await db.execute(stmt)
    row = result.first()
    return int(row[0]) if row else None


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


async def get_skills_summary(
    agent_uid: str, db: AsyncSession
) -> list[dict]:
    """取得 agent 關聯 skill 的 uid + name，軟刪除的 skill 不回傳。"""
    stmt = (
        select(Skill.skill_uid, Skill.name)
        .join(
            agent_skill_table,
            agent_skill_table.c.skill_uid == Skill.skill_uid,
        )
        .where(
            agent_skill_table.c.agent_uid == uuid.UUID(agent_uid),
            Skill.is_deleted == False,
        )
    )
    result = await db.execute(stmt)
    return [
        {"skill_uid": str(uid), "name": name}
        for uid, name in result.fetchall()
    ]


async def get_skills_summary_map(
    agent_uids: Iterable[str], db: AsyncSession
) -> dict[str, list[dict]]:
    """批次取得多個 agent 的 skill summary，避免列表查詢時逐項 N+1。"""
    uids = [uuid.UUID(a) for a in agent_uids]
    result: dict[str, list[dict]] = defaultdict(list)
    if not uids:
        return result

    stmt = (
        select(
            agent_skill_table.c.agent_uid,
            Skill.skill_uid,
            Skill.name,
        )
        .join(
            agent_skill_table,
            agent_skill_table.c.skill_uid == Skill.skill_uid,
        )
        .where(
            agent_skill_table.c.agent_uid.in_(uids),
            Skill.is_deleted == False,
        )
    )
    rows = await db.execute(stmt)
    for agent_uid, skill_uid, name in rows.fetchall():
        result[str(agent_uid)].append(
            {"skill_uid": str(skill_uid), "name": name}
        )
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
