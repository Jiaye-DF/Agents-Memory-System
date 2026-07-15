"""skill_embedding 1:N 向量表的資料存取層（v1.6.2 多向量架構）。"""

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill_embedding import SkillEmbedding


async def replace_for_skill(
    skill_uid: str,
    rows: list[tuple[str, list[float]]],
    db: AsyncSession,
) -> None:
    """同 transaction 全量替換該 skill 的向量 rows（delete + bulk insert）。

    `rows` 為 [(source_type, vector), ...]；不 commit，交由呼叫端決定。
    """
    await db.execute(
        delete(SkillEmbedding).where(SkillEmbedding.skill_uid == skill_uid)
    )
    db.add_all(
        [
            SkillEmbedding(
                skill_uid=skill_uid,
                source_type=source_type,
                embedding=vector,
            )
            for source_type, vector in rows
        ]
    )
    await db.flush()


async def hard_delete_by_skill(skill_uid: str, db: AsyncSession) -> int:
    """清除該 skill 全部向量 rows（備用清理介面），回傳刪除筆數。"""
    stmt = delete(SkillEmbedding).where(SkillEmbedding.skill_uid == skill_uid)
    result = await db.execute(stmt)
    return int(result.rowcount or 0)
