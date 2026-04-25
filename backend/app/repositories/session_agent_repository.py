"""session_agent 中介表 repository（v1.3.3 多 Agent 對話）。"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.session_agent import SessionAgent


async def get_pair(
    session_uid: str, agent_uid: str, db: AsyncSession
) -> SessionAgent | None:
    """取得指定 (session, agent) 的 row，含已軟刪資料供 add() 復活判斷。"""
    stmt = select(SessionAgent).where(
        SessionAgent.chat_session_uid == session_uid,
        SessionAgent.agent_uid == agent_uid,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def add(
    session_uid: str,
    agent_uid: str,
    db: AsyncSession,
    role: str = "member",
) -> SessionAgent:
    """加掛 agent 至 session；若該 (session, agent) 已軟刪則復活並更新 role。"""
    existing = await get_pair(session_uid, agent_uid, db)
    if existing is not None:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.role = role
            existing.is_active = True
            await db.flush()
            await db.refresh(existing)
            return existing
        # 已存在且有效：role 若不同則更新（呼叫者責任，這裡不主動衝撞 primary 唯一性）
        if existing.role != role:
            existing.role = role
            await db.flush()
            await db.refresh(existing)
        return existing

    row = SessionAgent(
        chat_session_uid=session_uid,
        agent_uid=agent_uid,
        role=role,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def remove(
    session_uid: str, agent_uid: str, db: AsyncSession
) -> bool:
    """軟刪除指定 (session, agent)；回傳是否成功命中。

    注意：本函式不處理 primary 移除後的 promote，由 service 層負責。
    """
    existing = await get_pair(session_uid, agent_uid, db)
    if existing is None or existing.is_deleted:
        return False
    existing.is_deleted = True
    await db.flush()
    return True


async def list_by_session(
    session_uid: str, db: AsyncSession
) -> list[tuple[SessionAgent, Agent | None]]:
    """列出 session 下所有有效掛載；以 (SessionAgent, Agent) tuple 回傳，方便補名稱。

    primary 排在前面，其餘以 created_at 升序（加入順序）。
    """
    stmt = (
        select(SessionAgent, Agent)
        .outerjoin(Agent, Agent.agent_uid == SessionAgent.agent_uid)
        .where(
            SessionAgent.chat_session_uid == session_uid,
            SessionAgent.is_deleted == False,  # noqa: E712
        )
        .order_by(
            # primary 在前
            (SessionAgent.role != "primary").asc(),
            SessionAgent.created_at.asc(),
            SessionAgent.pid.asc(),
        )
    )
    result = await db.execute(stmt)
    return [(sa, ag) for sa, ag in result.all()]


async def get_primary(
    session_uid: str, db: AsyncSession
) -> SessionAgent | None:
    """取 session 的 primary agent；多筆時取 created_at 最早者（避免 race 殘留）。"""
    stmt = (
        select(SessionAgent)
        .where(
            SessionAgent.chat_session_uid == session_uid,
            SessionAgent.is_deleted == False,  # noqa: E712
            SessionAgent.role == "primary",
        )
        .order_by(SessionAgent.created_at.asc(), SessionAgent.pid.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def is_member(
    session_uid: str, agent_uid: str, db: AsyncSession
) -> bool:
    """檢查 agent 是否為 session 的有效成員（含 primary / member）。"""
    stmt = select(SessionAgent.pid).where(
        SessionAgent.chat_session_uid == session_uid,
        SessionAgent.agent_uid == agent_uid,
        SessionAgent.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def count_active(session_uid: str, db: AsyncSession) -> int:
    """有效成員數（含 primary / member），用於上限與最後一個保護檢查。"""
    from sqlalchemy import func as _func

    stmt = (
        select(_func.count())
        .select_from(SessionAgent)
        .where(
            SessionAgent.chat_session_uid == session_uid,
            SessionAgent.is_deleted == False,  # noqa: E712
        )
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def set_primary(
    session_uid: str, agent_uid: str, db: AsyncSession
) -> SessionAgent:
    """將指定 agent 設為 primary，原 primary 改 member（同一 transaction）。

    需先把舊 primary 改為 member，再把目標改為 primary，以避開
    uq_session_agent_primary partial unique index 的衝突。
    """
    # 1) 先把所有現存 primary 改 member
    demote_stmt = (
        update(SessionAgent)
        .where(
            SessionAgent.chat_session_uid == session_uid,
            SessionAgent.is_deleted == False,  # noqa: E712
            SessionAgent.role == "primary",
        )
        .values(role="member")
    )
    await db.execute(demote_stmt)
    await db.flush()

    # 2) 把目標 (session, agent) 設為 primary（必須是有效成員）
    target = await get_pair(session_uid, agent_uid, db)
    if target is None or target.is_deleted:
        # 不存在或已軟刪：呼叫者應先 add()；這裡直接拋給 service 層處理
        raise ValueError("agent_not_in_session")
    target.role = "primary"
    await db.flush()
    await db.refresh(target)
    return target
