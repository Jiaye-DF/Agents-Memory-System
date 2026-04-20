from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_memory import ChatMemory


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


async def hard_delete_by_session(
    chat_session_uid: str, db: AsyncSession
) -> int:
    """Session 軟刪時連動清除記憶（hard delete）。"""
    stmt = delete(ChatMemory).where(
        ChatMemory.chat_session_uid == chat_session_uid
    )
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
