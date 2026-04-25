"""agentic_skill_suggestion repository（v1.3.6 Phase 1-3）。

職責：
- create：寫入新 suggestion（含 signature）
- find_active_signature：cooldown 判定（同 owner / scope / scope_uid / signature）
- list_by_owner：分頁列表（個人視角，支援 scope / status filter）
- list_pending_by_user：給 recommender 用的全 pending 清單
- mark_approved / mark_rejected / mark_expired_bulk：狀態變更
- get_by_uid：含擁有者驗證
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agentic_skill_suggestion import AgenticSkillSuggestion


async def create(
    suggestion_data: dict, db: AsyncSession
) -> AgenticSkillSuggestion:
    """寫入一筆新 suggestion。

    `suggestion_data` 期望欄位：
      owner_user_uid, scope, scope_uid, name, description, system_prompt,
      confidence (Decimal), source_memory_uids (list[uuid]), signature
    """
    suggestion = AgenticSkillSuggestion(**suggestion_data)
    db.add(suggestion)
    await db.flush()
    await db.refresh(suggestion)
    return suggestion


async def find_active_signature(
    *,
    owner_user_uid: str,
    scope: str,
    scope_uid: str,
    signature: str,
    cooldown_hours: int,
    db: AsyncSession,
) -> bool:
    """cooldown 判定：在 N 小時內是否已存在同 signature 的紀錄。

    對齊 task §0-3：cooldown 看 created_at，**不**限定 status，避免被剛 reject
    後再次大量重生（v1.1.7 PoC 觀察過該模式）。
    """
    sql = text(
        """
        SELECT 1
          FROM agentic_skill_suggestion
         WHERE owner_user_uid = :owner
           AND scope = :scope
           AND scope_uid = :scope_uid
           AND signature = :sig
           AND is_deleted = FALSE
           AND created_at > NOW() - (:hours || ' hours')::interval
         LIMIT 1
        """
    )
    result = await db.execute(
        sql,
        {
            "owner": uuid.UUID(owner_user_uid),
            "scope": scope,
            "scope_uid": uuid.UUID(scope_uid),
            "sig": signature,
            "hours": int(cooldown_hours),
        },
    )
    return result.first() is not None


async def list_by_owner(
    *,
    owner_user_uid: str,
    scope: str | None,
    status: str | None,
    page: int,
    size: int,
    db: AsyncSession,
) -> tuple[list[AgenticSkillSuggestion], int]:
    """個人列表（分頁）；status 預設 None 代表回所有狀態。

    依 created_at desc, pid desc 排序，pid 破平確保穩定分頁。
    """
    base = select(AgenticSkillSuggestion).where(
        AgenticSkillSuggestion.owner_user_uid == uuid.UUID(owner_user_uid),
        AgenticSkillSuggestion.is_deleted == False,  # noqa: E712
    )
    if scope is not None:
        base = base.where(AgenticSkillSuggestion.scope == scope)
    if status is not None:
        base = base.where(AgenticSkillSuggestion.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar() or 0)

    offset = max((page - 1) * size, 0)
    items_stmt = (
        base.order_by(
            AgenticSkillSuggestion.created_at.desc(),
            AgenticSkillSuggestion.pid.desc(),
        )
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(items_stmt)
    items = list(result.scalars().all())
    return items, total


async def list_pending_by_user(
    owner_user_uid: str,
    db: AsyncSession,
    *,
    min_confidence: Decimal | float | None = None,
) -> list[AgenticSkillSuggestion]:
    """給 recommender 用：列出該 user 所有 pending 中的 suggestion（可加 confidence 下限）。"""
    stmt = select(AgenticSkillSuggestion).where(
        AgenticSkillSuggestion.owner_user_uid == uuid.UUID(owner_user_uid),
        AgenticSkillSuggestion.status == "pending",
        AgenticSkillSuggestion.is_deleted == False,  # noqa: E712
    )
    if min_confidence is not None:
        stmt = stmt.where(
            AgenticSkillSuggestion.confidence >= Decimal(str(min_confidence))
        )
    stmt = stmt.order_by(AgenticSkillSuggestion.confidence.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_uid(
    suggestion_uid: str,
    owner_user_uid: str,
    db: AsyncSession,
) -> AgenticSkillSuggestion | None:
    """含擁有者驗證的取詳情：找不到或非擁有者皆回 None。"""
    stmt = select(AgenticSkillSuggestion).where(
        AgenticSkillSuggestion.agentic_skill_suggestion_uid
        == uuid.UUID(suggestion_uid),
        AgenticSkillSuggestion.owner_user_uid == uuid.UUID(owner_user_uid),
        AgenticSkillSuggestion.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def mark_approved(
    suggestion: AgenticSkillSuggestion,
    created_skill_uid: str,
    db: AsyncSession,
) -> AgenticSkillSuggestion:
    suggestion.status = "approved"
    suggestion.created_skill_uid = uuid.UUID(created_skill_uid)
    await db.flush()
    await db.refresh(suggestion)
    return suggestion


async def mark_rejected(
    suggestion: AgenticSkillSuggestion, db: AsyncSession
) -> AgenticSkillSuggestion:
    suggestion.status = "rejected"
    await db.flush()
    await db.refresh(suggestion)
    return suggestion


async def mark_expired_bulk(
    cutoff_at: datetime, db: AsyncSession
) -> int:
    """將 created_at 早於 cutoff 且仍 pending 的 suggestion 標為 expired。

    供 list API lazy 標記用（不需獨立 worker）；回傳 affected row count。
    """
    stmt = (
        update(AgenticSkillSuggestion)
        .where(
            AgenticSkillSuggestion.status == "pending",
            AgenticSkillSuggestion.created_at < cutoff_at,
            AgenticSkillSuggestion.is_deleted == False,  # noqa: E712
        )
        .values(status="expired")
    )
    result = await db.execute(stmt)
    return int(result.rowcount or 0)
