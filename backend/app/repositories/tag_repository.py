"""`tag` 表的資料存取層。

per-user 隔離；查詢含 `usage_count` 時 LEFT JOIN `entity_tag` 一次撈完，
避免 N+1。同名 case-insensitive 比對統一走 `func.lower(name)`。
"""

from __future__ import annotations

import uuid

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity_tag import EntityTag
from app.models.tag import Tag


async def get_by_uid(tag_uid: str, db: AsyncSession) -> Tag | None:
    stmt = select(Tag).where(
        Tag.tag_uid == uuid.UUID(tag_uid),
        Tag.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_uid_any(tag_uid: str, db: AsyncSession) -> Tag | None:
    """含軟刪，給 find-or-create 復活用。"""
    stmt = select(Tag).where(Tag.tag_uid == uuid.UUID(tag_uid))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_owner_name_any(
    owner_user_uid: str, name: str, db: AsyncSession
) -> Tag | None:
    """同擁有者 case-insensitive 比對，含軟刪。給 find-or-create 復活用。"""
    stmt = select(Tag).where(
        Tag.owner_user_uid == uuid.UUID(owner_user_uid),
        func.lower(Tag.name) == name.strip().lower(),
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def list_by_owner(
    owner_user_uid: str,
    q: str | None,
    db: AsyncSession,
    limit: int = 200,
) -> list[tuple[Tag, int]]:
    """列出使用者未軟刪的 tag，含 usage_count。

    回傳 `[(Tag, usage_count)]`，依 `usage_count DESC, name ASC` 排序。
    `q` 非空時做 `lower(name) LIKE %q%` 模糊搜尋（autocomplete 用）。
    """
    # 只算未軟刪的 entity_tag
    alive_count = func.count(
        case((EntityTag.is_deleted == False, EntityTag.pid))  # noqa: E712
    )

    stmt = (
        select(Tag, alive_count.label("usage_count"))
        .outerjoin(EntityTag, EntityTag.tag_uid == Tag.tag_uid)
        .where(
            Tag.owner_user_uid == uuid.UUID(owner_user_uid),
            Tag.is_deleted == False,  # noqa: E712
        )
        .group_by(Tag.pid)
        .order_by(alive_count.desc(), Tag.name.asc())
        .limit(limit)
    )

    if q:
        stmt = stmt.where(func.lower(Tag.name).like(f"%{q.strip().lower()}%"))

    result = await db.execute(stmt)
    return [(row[0], int(row[1] or 0)) for row in result.all()]


async def create(
    owner_user_uid: str, name: str, db: AsyncSession
) -> Tag:
    tag = Tag(
        owner_user_uid=uuid.UUID(owner_user_uid),
        name=name.strip(),
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return tag


async def revive(tag: Tag, db: AsyncSession) -> Tag:
    """軟刪 tag 復活，重新置為 active。"""
    tag.is_deleted = False
    tag.is_active = True
    await db.flush()
    await db.refresh(tag)
    return tag


async def rename(tag: Tag, new_name: str, db: AsyncSession) -> Tag:
    tag.name = new_name.strip()
    await db.flush()
    await db.refresh(tag)
    return tag


async def soft_delete(tag: Tag, db: AsyncSession) -> None:
    tag.is_deleted = True
    await db.flush()


async def get_by_uids(
    tag_uids: list[str], db: AsyncSession
) -> list[Tag]:
    if not tag_uids:
        return []
    uuids = [uuid.UUID(u) for u in tag_uids]
    stmt = select(Tag).where(
        Tag.tag_uid.in_(uuids),
        Tag.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
