from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession


async def get_by_uid(
    chat_session_uid: str, db: AsyncSession
) -> ChatSession | None:
    stmt = select(ChatSession).where(
        ChatSession.chat_session_uid == chat_session_uid,
        ChatSession.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def stmt_by_project(chat_project_uid: str) -> Select[tuple[ChatSession]]:
    return select(ChatSession).where(
        ChatSession.is_deleted == False,
        ChatSession.chat_project_uid == chat_project_uid,
    )


async def count_by_project(
    chat_project_uid: str, db: AsyncSession
) -> int:
    stmt = select(func.count()).select_from(ChatSession).where(
        ChatSession.is_deleted == False,
        ChatSession.chat_project_uid == chat_project_uid,
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def message_stats_map(
    chat_session_uids: list[str], db: AsyncSession
) -> dict[str, tuple[int, object | None]]:
    """回傳 { session_uid: (message_count, last_created_at) }"""
    if not chat_session_uids:
        return {}
    stmt = (
        select(
            ChatMessage.chat_session_uid,
            func.count(ChatMessage.pid),
            func.max(ChatMessage.created_at),
        )
        .where(ChatMessage.chat_session_uid.in_(chat_session_uids))
        .group_by(ChatMessage.chat_session_uid)
    )
    rows = await db.execute(stmt)
    return {
        str(session_uid): (int(count), last_at)
        for session_uid, count, last_at in rows.fetchall()
    }


async def create(session_data: dict, db: AsyncSession) -> ChatSession:
    session = ChatSession(**session_data)
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def update(
    session: ChatSession, update_data: dict, db: AsyncSession
) -> ChatSession:
    for key, value in update_data.items():
        setattr(session, key, value)
    await db.flush()
    await db.refresh(session)
    return session


async def soft_delete(session: ChatSession, db: AsyncSession) -> None:
    session.is_deleted = True
    await db.flush()
