"""`user_favorite` 表的資料存取層。

資源表（agent / skill / script）計數欄位的 +/- 1 由 service 層透過
`favorite_service._dispatch_count_update` 統一 dispatch，此模組只負責
`user_favorite` 自身的 CRUD 與查詢。
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_favorite import UserFavorite


async def get_alive(
    owner_user_uid: str,
    resource_type: str,
    resource_uid: str,
    db: AsyncSession,
) -> UserFavorite | None:
    """取得未軟刪的收藏紀錄（若存在）。"""
    stmt = select(UserFavorite).where(
        UserFavorite.owner_user_uid == uuid.UUID(owner_user_uid),
        UserFavorite.resource_type == resource_type,
        UserFavorite.resource_uid == uuid.UUID(resource_uid),
        UserFavorite.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_any(
    owner_user_uid: str,
    resource_type: str,
    resource_uid: str,
    db: AsyncSession,
) -> UserFavorite | None:
    """取得任一狀態的收藏紀錄（含軟刪除）。用於 UPSERT 復活場景。"""
    stmt = select(UserFavorite).where(
        UserFavorite.owner_user_uid == uuid.UUID(owner_user_uid),
        UserFavorite.resource_type == resource_type,
        UserFavorite.resource_uid == uuid.UUID(resource_uid),
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def add(
    owner_user_uid: str,
    resource_type: str,
    resource_uid: str,
    db: AsyncSession,
) -> tuple[UserFavorite, bool]:
    """新增 / 復活收藏紀錄。

    回傳 `(favorite, is_new_or_revived)`：
    - 若未存在 → 新增，is_new_or_revived=True
    - 若存在但 is_deleted=True → 復活（is_deleted=False），is_new_or_revived=True
    - 若已存在且未刪 → 不動作，is_new_or_revived=False（idempotent）
    """
    existing = await get_any(owner_user_uid, resource_type, resource_uid, db)
    if existing is None:
        fav = UserFavorite(
            owner_user_uid=uuid.UUID(owner_user_uid),
            resource_type=resource_type,
            resource_uid=uuid.UUID(resource_uid),
        )
        db.add(fav)
        await db.flush()
        await db.refresh(fav)
        return fav, True

    if existing.is_deleted:
        existing.is_deleted = False
        existing.is_active = True
        await db.flush()
        await db.refresh(existing)
        return existing, True

    return existing, False


async def remove(
    owner_user_uid: str,
    resource_type: str,
    resource_uid: str,
    db: AsyncSession,
) -> bool:
    """軟刪收藏紀錄。回傳是否真的有刪到（idempotent 判斷用）。"""
    existing = await get_alive(owner_user_uid, resource_type, resource_uid, db)
    if existing is None:
        return False
    existing.is_deleted = True
    await db.flush()
    return True


async def list_by_owner(
    owner_user_uid: str,
    resource_type: str | None,
    page: int,
    size: int,
    db: AsyncSession,
) -> tuple[list[UserFavorite], int]:
    """列出使用者的收藏（未軟刪）。

    回傳 `(items, total)`。依 `created_at desc, pid desc` 排序，
    `created_at` 相同時以 pid 破平保證穩定分頁。
    """
    base = select(UserFavorite).where(
        UserFavorite.owner_user_uid == uuid.UUID(owner_user_uid),
        UserFavorite.is_deleted == False,  # noqa: E712
    )
    if resource_type is not None:
        base = base.where(UserFavorite.resource_type == resource_type)

    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar() or 0)

    offset = max((page - 1) * size, 0)
    items_stmt = (
        base.order_by(UserFavorite.created_at.desc(), UserFavorite.pid.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(items_stmt)
    items = list(result.scalars().all())
    return items, total


async def is_favorited_bulk(
    owner_user_uid: str | None,
    resource_type: str,
    resource_uids: list[str],
    db: AsyncSession,
) -> set[str]:
    """批次判斷使用者對多個資源是否已收藏。

    未登入 / 空列表 / owner_user_uid 為 None 時回傳空集合。
    回傳 `set[str]` 包含已收藏的 resource_uid（以 str 形式）。
    """
    if not owner_user_uid or not resource_uids:
        return set()

    uuids = [uuid.UUID(u) for u in resource_uids]
    stmt = select(UserFavorite.resource_uid).where(
        UserFavorite.owner_user_uid == uuid.UUID(owner_user_uid),
        UserFavorite.resource_type == resource_type,
        UserFavorite.resource_uid.in_(uuids),
        UserFavorite.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    return {str(row[0]) for row in result.fetchall()}
