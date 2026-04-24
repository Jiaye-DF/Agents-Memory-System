"""Script 資料存取層。

與 Skill 差異：
- Script 無 `visibility` 欄位（v1.2 僅擁有者可見，跨使用者可見性留 v1.4）
- 僅擁有者能操作，故 `list_by_owner` 直接以 owner_user_uid 過濾
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.script import Script


def _greatest_zero(expr):
    return func.greatest(expr, 0)


async def get_by_uid(script_uid: str, db: AsyncSession) -> Script | None:
    stmt = select(Script).where(
        Script.script_uid == uuid.UUID(script_uid),
        Script.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def stmt_owned_by_user(owner_user_uid: str) -> Select[tuple[Script]]:
    """v1.2 Script 尚未開放跨使用者可見，僅回傳擁有者自己的資料。"""
    return select(Script).where(
        Script.is_deleted == False,  # noqa: E712
        Script.owner_user_uid == uuid.UUID(owner_user_uid),
    )


ALLOWED_ORDER_FIELDS = {
    "favorite_count": Script.favorite_count,
    "download_count": Script.download_count,
    "created_at": Script.created_at,
    "updated_at": Script.updated_at,
}


def get_order_column(order_by: str | None):
    """白名單驗證後回傳 SQLAlchemy 欄位；未指定時預設 `created_at`。"""
    key = order_by or "created_at"
    if key not in ALLOWED_ORDER_FIELDS:
        raise ValueError(f"不支援的 order_by：{order_by}")
    return ALLOWED_ORDER_FIELDS[key]


async def create(script_data: dict, db: AsyncSession) -> Script:
    script = Script(**script_data)
    db.add(script)
    await db.flush()
    await db.refresh(script)
    return script


async def update_obj(
    script: Script, update_data: dict, db: AsyncSession
) -> Script:
    for key, value in update_data.items():
        setattr(script, key, value)
    await db.flush()
    await db.refresh(script)
    return script


async def soft_delete(script: Script, db: AsyncSession) -> None:
    script.is_deleted = True
    await db.flush()


async def count_by_owner(
    owner_user_uid: str, db: AsyncSession
) -> int:
    stmt = select(func.count()).select_from(
        select(Script)
        .where(
            Script.is_deleted == False,  # noqa: E712
            Script.owner_user_uid == uuid.UUID(owner_user_uid),
        )
        .subquery()
    )
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def exists_name_for_owner(
    owner_user_uid: str,
    name: str,
    db: AsyncSession,
    exclude_script_uid: str | None = None,
) -> bool:
    """檢查同 owner 是否已有未軟刪的同名 Script。用於 create/update 前快速驗證。"""
    stmt = select(Script.pid).where(
        Script.is_deleted == False,  # noqa: E712
        Script.owner_user_uid == uuid.UUID(owner_user_uid),
        Script.name == name,
    )
    if exclude_script_uid is not None:
        stmt = stmt.where(Script.script_uid != uuid.UUID(exclude_script_uid))
    result = await db.execute(stmt.limit(1))
    return result.scalar_one_or_none() is not None


async def increment_favorite_count(
    script_uid: str, delta: int, db: AsyncSession
) -> int | None:
    stmt = (
        update(Script)
        .where(
            Script.script_uid == uuid.UUID(script_uid),
            Script.is_deleted == False,  # noqa: E712
        )
        .values(
            favorite_count=_greatest_zero(Script.favorite_count + delta)
        )
        .returning(Script.favorite_count)
    )
    result = await db.execute(stmt)
    row = result.first()
    return int(row[0]) if row else None


async def increment_download_count(
    script_uid: str, delta: int, db: AsyncSession
) -> int | None:
    stmt = (
        update(Script)
        .where(
            Script.script_uid == uuid.UUID(script_uid),
            Script.is_deleted == False,  # noqa: E712
        )
        .values(download_count=Script.download_count + delta)
        .returning(Script.download_count)
    )
    result = await db.execute(stmt)
    row = result.first()
    return int(row[0]) if row else None


async def get_by_uids(
    script_uids: list[str], db: AsyncSession, include_deleted: bool = False
) -> list[Script]:
    """批次取得多個 Script（給我的收藏 tombstone 判讀用）。"""
    if not script_uids:
        return []
    uuids = [uuid.UUID(u) for u in script_uids]
    stmt = select(Script).where(Script.script_uid.in_(uuids))
    if not include_deleted:
        stmt = stmt.where(Script.is_deleted == False)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())
