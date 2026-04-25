"""project_memory repository（v1.3.5 Phase 2-1）。

職責：
- create / list / search_similar（cosine + min_score）
- count_by_project：給 worker 判斷是否達聚合門檻
- hard_delete_by_project：給 service 層連動清除（propose §3-3）
"""

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project_memory import ProjectMemory


async def create(memory_data: dict, db: AsyncSession) -> ProjectMemory:
    memory = ProjectMemory(**memory_data)
    db.add(memory)
    await db.flush()
    await db.refresh(memory)
    return memory


async def list_by_project(
    chat_project_uid: str, db: AsyncSession
) -> list[ProjectMemory]:
    stmt = (
        select(ProjectMemory)
        .where(ProjectMemory.chat_project_uid == chat_project_uid)
        .order_by(ProjectMemory.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_by_project(
    chat_project_uid: str, db: AsyncSession
) -> int:
    stmt = (
        select(func.count())
        .select_from(ProjectMemory)
        .where(ProjectMemory.chat_project_uid == chat_project_uid)
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def hard_delete_by_project(
    chat_project_uid: str, db: AsyncSession
) -> int:
    """Project 刪除連動清除（hard delete，propose §3-3）。"""
    stmt = delete(ProjectMemory).where(
        ProjectMemory.chat_project_uid == chat_project_uid
    )
    result = await db.execute(stmt)
    return int(result.rowcount or 0)


async def search_similar(
    chat_project_uid: str,
    query_embedding: list[float],
    top_k: int,
    min_score: float,
    db: AsyncSession,
) -> list[tuple[ProjectMemory, float]]:
    """三層 RAG（project 層）向量檢索；對齊 chat_memory_repository.search_similar 形式。"""
    vector_literal = (
        "[" + ",".join(repr(float(x)) for x in query_embedding) + "]"
    )

    sql = text(
        """
        SELECT pid,
               project_memory_uid,
               chat_project_uid,
               source_session_uids,
               source_chat_message_uids,
               keywords,
               entities,
               topic,
               created_at,
               1 - (embedding <=> CAST(:query AS vector)) AS score
        FROM project_memory
        WHERE chat_project_uid = :project_uid
          AND 1 - (embedding <=> CAST(:query AS vector)) >= :min_score
        ORDER BY embedding <=> CAST(:query AS vector)
        LIMIT :top_k
        """
    )
    result = await db.execute(
        sql,
        {
            "query": vector_literal,
            "project_uid": chat_project_uid,
            "min_score": min_score,
            "top_k": top_k,
        },
    )
    rows = result.mappings().all()
    out: list[tuple[ProjectMemory, float]] = []
    for row in rows:
        mem = ProjectMemory(
            pid=row["pid"],
            project_memory_uid=row["project_memory_uid"],
            chat_project_uid=row["chat_project_uid"],
            source_session_uids=list(row["source_session_uids"] or []),
            source_chat_message_uids=list(row["source_chat_message_uids"] or []),
            keywords=list(row["keywords"] or []),
            entities=list(row["entities"] or []),
            topic=row["topic"],
            created_at=row["created_at"],
            embedding=[],
        )
        out.append((mem, float(row["score"])))
    return out
