import uuid

from sqlalchemy import Select, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill


def _greatest_zero(expr):
    return func.greatest(expr, 0)


async def get_by_uid(skill_uid: str, db: AsyncSession) -> Skill | None:
    stmt = select(Skill).where(
        Skill.skill_uid == skill_uid,
        Skill.is_deleted == False,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def stmt_visible_to_user(user_uid: str) -> Select[tuple[Skill]]:
    return select(Skill).where(
        Skill.is_deleted == False,
        or_(
            Skill.owner_user_uid == user_uid,
            Skill.visibility == "public",
        ),
    )


ALLOWED_ORDER_FIELDS = {
    "favorite_count": Skill.favorite_count,
    "download_count": Skill.download_count,
    "created_at": Skill.created_at,
    "updated_at": Skill.updated_at,
}


def get_order_column(order_by: str | None):
    """白名單驗證後回傳 SQLAlchemy 欄位；未指定時預設 `created_at`。"""
    key = order_by or "created_at"
    if key not in ALLOWED_ORDER_FIELDS:
        raise ValueError(f"不支援的 order_by：{order_by}")
    return ALLOWED_ORDER_FIELDS[key]


async def create(skill_data: dict, db: AsyncSession) -> Skill:
    skill = Skill(**skill_data)
    db.add(skill)
    await db.flush()
    await db.refresh(skill)
    return skill


async def update_obj(skill: Skill, update_data: dict, db: AsyncSession) -> Skill:
    for key, value in update_data.items():
        setattr(skill, key, value)
    await db.flush()
    await db.refresh(skill)
    return skill


async def soft_delete(skill: Skill, db: AsyncSession) -> None:
    skill.is_deleted = True
    await db.flush()


async def increment_favorite_count(
    skill_uid: str, delta: int, db: AsyncSession
) -> int | None:
    stmt = (
        update(Skill)
        .where(
            Skill.skill_uid == uuid.UUID(skill_uid),
            Skill.is_deleted == False,  # noqa: E712
        )
        .values(
            favorite_count=_greatest_zero(Skill.favorite_count + delta)
        )
        .returning(Skill.favorite_count)
    )
    result = await db.execute(stmt)
    row = result.first()
    return int(row[0]) if row else None


async def increment_download_count(
    skill_uid: str, delta: int, db: AsyncSession
) -> int | None:
    stmt = (
        update(Skill)
        .where(
            Skill.skill_uid == uuid.UUID(skill_uid),
            Skill.is_deleted == False,  # noqa: E712
        )
        .values(download_count=Skill.download_count + delta)
        .returning(Skill.download_count)
    )
    result = await db.execute(stmt)
    row = result.first()
    return int(row[0]) if row else None


async def get_by_uids(
    skill_uids: list[str], db: AsyncSession, include_deleted: bool = False
) -> list[Skill]:
    """批次取得多個 skill（保留順序需呼叫端自行處理）。

    `include_deleted=True` 用於「我的收藏」列表：即使目標已軟刪，仍需找到 row
    以判讀 tombstone 狀態。
    """
    if not skill_uids:
        return []
    uuids = [uuid.UUID(u) for u in skill_uids]
    stmt = select(Skill).where(Skill.skill_uid.in_(uuids))
    if not include_deleted:
        stmt = stmt.where(Skill.is_deleted == False)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().all())


# 內層近鄰候選數 = top_k * 6：涵蓋同 skill 多 row（最多 3 條向量）與可見性過濾損耗
CANDIDATE_MULTIPLIER = 6


async def search_similar(
    query_embedding: list[float],
    top_k: int,
    min_score: float,
    user_uid: str,
    db: AsyncSession,
    scope: str = "visible",
) -> list[tuple[Skill, float]]:
    """pgvector cosine 語意檢索（v1.6.2 多向量）：兩層 SQL——內層對 skill_embedding
    純 HNSW 近鄰取候選，外層 join skill 過濾後 per-skill 取 MAX 分數，門檻作用在
    MAX 上；raw SQL 取 skill_uid + score 保序，再以 ORM 補完整 Skill（含 owner）。

    `scope="public"` 時可見性條款僅取 `visibility = 'public'`（公開市集用，
    不含 owner 條件）；其餘值（含未知值防呆）一律視為 `"visible"`（v1.6.0 原行為）。
    """
    vector_literal = "[" + ",".join(repr(float(x)) for x in query_embedding) + "]"

    if scope == "public":
        visibility_clause = "s.visibility = 'public'"
        params: dict = {}
    else:
        visibility_clause = (
            "(s.owner_user_uid = CAST(:user_uid AS uuid) OR s.visibility = 'public')"
        )
        params = {"user_uid": str(uuid.UUID(user_uid))}

    sql = text(
        f"""
        SELECT t.skill_uid, MAX(t.score) AS score
        FROM (
            SELECT se.skill_uid,
                   1 - (se.embedding <=> CAST(:query AS vector)) AS score
            FROM skill_embedding se
            ORDER BY se.embedding <=> CAST(:query AS vector)
            LIMIT :candidate_k
        ) t
        JOIN skill s ON s.skill_uid = t.skill_uid
        WHERE s.is_deleted = FALSE
          AND {visibility_clause}
        GROUP BY t.skill_uid
        HAVING MAX(t.score) >= :min_score
        ORDER BY score DESC
        LIMIT :top_k
        """
    )
    result = await db.execute(
        sql,
        {
            "query": vector_literal,
            "min_score": min_score,
            "candidate_k": top_k * CANDIDATE_MULTIPLIER,
            "top_k": top_k,
            **params,
        },
    )
    rows = result.mappings().all()
    if not rows:
        return []
    scores = {row["skill_uid"]: float(row["score"]) for row in rows}
    stmt = select(Skill).where(Skill.skill_uid.in_(scores.keys()))
    skills = {
        skill.skill_uid: skill
        for skill in (await db.execute(stmt)).scalars().all()
    }
    return [
        (skills[row["skill_uid"]], scores[row["skill_uid"]])
        for row in rows
        if row["skill_uid"] in skills
    ]
