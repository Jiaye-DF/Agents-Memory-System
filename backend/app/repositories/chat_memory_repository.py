from datetime import datetime

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_memory import ChatMemory
from app.models.chat_session import ChatSession


async def create(memory_data: dict, db: AsyncSession) -> ChatMemory:
    memory = ChatMemory(**memory_data)
    db.add(memory)
    await db.flush()
    await db.refresh(memory)
    return memory


async def list_by_session(
    chat_session_uid: str, db: AsyncSession
) -> list[ChatMemory]:
    stmt = (
        select(ChatMemory)
        .where(ChatMemory.chat_session_uid == chat_session_uid)
        .order_by(ChatMemory.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_by_project(
    chat_project_uid: str, db: AsyncSession
) -> list[ChatMemory]:
    """JOIN chat_session 取該 project 下所有 session 的 chat_memory。

    給 project_memory_worker 二次聚合用（v1.3.5 Phase 3）。
    軟刪除過的 session 仍納入（chat_memory 隨 session 軟刪時會被 hard delete，
    所以「存在」即代表 session 仍有效）。
    """
    stmt = (
        select(ChatMemory)
        .join(
            ChatSession,
            ChatSession.chat_session_uid == ChatMemory.chat_session_uid,
        )
        .where(
            ChatSession.chat_project_uid == chat_project_uid,
            ChatSession.is_deleted == False,
        )
        .order_by(ChatMemory.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_by_user(
    owner_user_uid: str,
    db: AsyncSession,
    since: datetime | None = None,
) -> list[ChatMemory]:
    """JOIN chat_session 取該 user 所有 session 的 chat_memory。

    給 user_memory_worker 跨 project 偏好聚合用（v1.3.5 Phase 4）。
    `since` 指定後僅回 created_at >= since 的記憶（時間窗，預設 30 天）。
    """
    conditions = [
        ChatSession.owner_user_uid == owner_user_uid,
        ChatSession.is_deleted == False,
    ]
    if since is not None:
        conditions.append(ChatMemory.created_at >= since)
    stmt = (
        select(ChatMemory)
        .join(
            ChatSession,
            ChatSession.chat_session_uid == ChatMemory.chat_session_uid,
        )
        .where(*conditions)
        .order_by(ChatMemory.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def hard_delete_by_session(
    chat_session_uid: str, db: AsyncSession
) -> int:
    """Session 軟刪時連動清除記憶（hard delete）。"""
    stmt = delete(ChatMemory).where(
        ChatMemory.chat_session_uid == chat_session_uid
    )
    result = await db.execute(stmt)
    return int(result.rowcount or 0)


async def hard_delete_by_project(
    chat_project_uid: str, db: AsyncSession
) -> int:
    """Project 刪除連動：清該 project 下所有 session 的 chat_memory（v1.3.5 Phase 6）。

    走子查詢取 session_uid（不依賴 ORM relationship），對齊 propose §3-3 表格。
    """
    subq = (
        select(ChatSession.chat_session_uid)
        .where(ChatSession.chat_project_uid == chat_project_uid)
        .scalar_subquery()
    )
    stmt = delete(ChatMemory).where(ChatMemory.chat_session_uid.in_(subq))
    result = await db.execute(stmt)
    return int(result.rowcount or 0)


async def hard_delete_by_user(
    owner_user_uid: str, db: AsyncSession
) -> int:
    """User 停用 / 刪除連動：清該 user 全部 chat_memory（v1.3.5 Phase 6）。"""
    subq = (
        select(ChatSession.chat_session_uid)
        .where(ChatSession.owner_user_uid == owner_user_uid)
        .scalar_subquery()
    )
    stmt = delete(ChatMemory).where(ChatMemory.chat_session_uid.in_(subq))
    result = await db.execute(stmt)
    return int(result.rowcount or 0)


async def search_similar(
    chat_session_uid: str,
    query_embedding: list[float],
    top_k: int,
    min_score: float,
    db: AsyncSession,
) -> list[tuple[ChatMemory, float]]:
    """
    使用 pgvector cosine 運算子 <=> 查詢相似記憶。
    回傳 [(memory, score)]，score 為 1 - cosine_distance（越高越相似）。
    """
    # pgvector 對 embedding 參數需轉字串格式："[0.1,0.2,...]"
    vector_literal = "[" + ",".join(repr(float(x)) for x in query_embedding) + "]"

    sql = text(
        """
        SELECT pid,
               chat_memory_uid,
               chat_session_uid,
               source_chat_message_uids,
               keywords,
               entities,
               topic,
               created_at,
               1 - (embedding <=> CAST(:query AS vector)) AS score
        FROM chat_memory
        WHERE chat_session_uid = :session_uid
          AND 1 - (embedding <=> CAST(:query AS vector)) >= :min_score
        ORDER BY embedding <=> CAST(:query AS vector)
        LIMIT :top_k
        """
    )
    result = await db.execute(
        sql,
        {
            "query": vector_literal,
            "session_uid": chat_session_uid,
            "min_score": min_score,
            "top_k": top_k,
        },
    )
    rows = result.mappings().all()
    out: list[tuple[ChatMemory, float]] = []
    for row in rows:
        mem = ChatMemory(
            pid=row["pid"],
            chat_memory_uid=row["chat_memory_uid"],
            chat_session_uid=row["chat_session_uid"],
            source_chat_message_uids=list(row["source_chat_message_uids"] or []),
            keywords=list(row["keywords"] or []),
            entities=list(row["entities"] or []),
            topic=row["topic"],
            created_at=row["created_at"],
            embedding=[],  # 查詢不回傳 embedding，省流量
        )
        out.append((mem, float(row["score"])))
    return out
