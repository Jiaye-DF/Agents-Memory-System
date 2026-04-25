"""user_memory repository（v1.3.5 Phase 2-2）。

職責：
- create / list / search_similar（cosine + min_score）
- count_by_user：給 worker 判斷是否達聚合門檻
- hard_delete_by_user：給 service 層連動清除（propose §3-3）
"""

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_memory import UserMemory


async def create(memory_data: dict, db: AsyncSession) -> UserMemory:
    memory = UserMemory(**memory_data)
    db.add(memory)
    await db.flush()
    await db.refresh(memory)
    return memory


async def list_by_user(
    owner_user_uid: str, db: AsyncSession
) -> list[UserMemory]:
    stmt = (
        select(UserMemory)
        .where(UserMemory.owner_user_uid == owner_user_uid)
        .order_by(UserMemory.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_by_user(owner_user_uid: str, db: AsyncSession) -> int:
    stmt = (
        select(func.count())
        .select_from(UserMemory)
        .where(UserMemory.owner_user_uid == owner_user_uid)
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def hard_delete_by_user(
    owner_user_uid: str, db: AsyncSession
) -> int:
    """User 停用 / 刪除連動清除（hard delete，propose §3-3）。"""
    stmt = delete(UserMemory).where(
        UserMemory.owner_user_uid == owner_user_uid
    )
    result = await db.execute(stmt)
    return int(result.rowcount or 0)


async def search_similar(
    owner_user_uid: str,
    query_embedding: list[float],
    top_k: int,
    min_score: float,
    db: AsyncSession,
) -> list[tuple[UserMemory, float]]:
    """三層 RAG（user 層）向量檢索；對齊 chat_memory_repository.search_similar 形式。"""
    vector_literal = (
        "[" + ",".join(repr(float(x)) for x in query_embedding) + "]"
    )

    sql = text(
        """
        SELECT pid,
               user_memory_uid,
               owner_user_uid,
               source_session_uids,
               source_project_uids,
               keywords,
               entities,
               topic,
               created_at,
               1 - (embedding <=> CAST(:query AS vector)) AS score
        FROM user_memory
        WHERE owner_user_uid = :user_uid
          AND 1 - (embedding <=> CAST(:query AS vector)) >= :min_score
        ORDER BY embedding <=> CAST(:query AS vector)
        LIMIT :top_k
        """
    )
    result = await db.execute(
        sql,
        {
            "query": vector_literal,
            "user_uid": owner_user_uid,
            "min_score": min_score,
            "top_k": top_k,
        },
    )
    rows = result.mappings().all()
    out: list[tuple[UserMemory, float]] = []
    for row in rows:
        mem = UserMemory(
            pid=row["pid"],
            user_memory_uid=row["user_memory_uid"],
            owner_user_uid=row["owner_user_uid"],
            source_session_uids=list(row["source_session_uids"] or []),
            source_project_uids=list(row["source_project_uids"] or []),
            keywords=list(row["keywords"] or []),
            entities=list(row["entities"] or []),
            topic=row["topic"],
            created_at=row["created_at"],
            embedding=[],
        )
        out.append((mem, float(row["score"])))
    return out
