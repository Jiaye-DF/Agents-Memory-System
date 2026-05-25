"""`entity_tag` 泛型中介表的資料存取層。

跨 skill / script / agent 共用，FK 走「邏輯外鍵 + service 一致性」模式
（沿用 [user_favorite_repository.py](user_favorite_repository.py) 的解耦風格）。

關鍵 API：
- `get_tags_bulk`：給 list endpoint 一次撈所有 entity 的 tag，避免 N+1
- `set_entity_tags`：整批替換 entity 的 tag（idempotent 復活 / 軟刪 diff）
- `apply_tag_filter`：給三 entity repo 共用的 AND filter helper
- `soft_delete_by_tag`：刪 tag 時 service 連動軟刪
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity_tag import EntityTag
from app.models.tag import Tag


async def list_alive_by_entity(
    entity_type: str,
    entity_uid: str,
    db: AsyncSession,
) -> list[tuple[uuid.UUID, str]]:
    """回傳 entity 上未軟刪的 (tag_uid, tag_name) 列表，依 name ASC。"""
    stmt = (
        select(Tag.tag_uid, Tag.name)
        .join(EntityTag, EntityTag.tag_uid == Tag.tag_uid)
        .where(
            EntityTag.entity_type == entity_type,
            EntityTag.entity_uid == uuid.UUID(entity_uid),
            EntityTag.is_deleted == False,  # noqa: E712
            Tag.is_deleted == False,  # noqa: E712
        )
        .order_by(Tag.name.asc())
    )
    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def get_tags_bulk(
    entity_type: str,
    entity_uids: list[str],
    db: AsyncSession,
) -> dict[str, list[dict]]:
    """批次取多個 entity 的 tags，回 `{entity_uid_str: [{tag_uid, name}]}`。

    空陣列直接回空 dict；單次查詢取代 N+1。
    """
    if not entity_uids:
        return {}

    uuids = [uuid.UUID(u) for u in entity_uids]
    stmt = (
        select(EntityTag.entity_uid, Tag.tag_uid, Tag.name)
        .join(Tag, Tag.tag_uid == EntityTag.tag_uid)
        .where(
            EntityTag.entity_type == entity_type,
            EntityTag.entity_uid.in_(uuids),
            EntityTag.is_deleted == False,  # noqa: E712
            Tag.is_deleted == False,  # noqa: E712
        )
        .order_by(EntityTag.entity_uid, Tag.name.asc())
    )

    result = await db.execute(stmt)
    out: dict[str, list[dict]] = {str(u): [] for u in entity_uids}
    for entity_uid, tag_uid, name in result.all():
        out[str(entity_uid)].append({"tag_uid": str(tag_uid), "name": name})
    return out


async def _get_existing_assignment(
    tag_uid: uuid.UUID,
    entity_type: str,
    entity_uid: uuid.UUID,
    db: AsyncSession,
) -> EntityTag | None:
    """取任一狀態（含軟刪）的綁定 row。Partial Unique 保證最多一筆。"""
    stmt = select(EntityTag).where(
        EntityTag.tag_uid == tag_uid,
        EntityTag.entity_type == entity_type,
        EntityTag.entity_uid == entity_uid,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def set_entity_tags(
    entity_type: str,
    entity_uid: str,
    target_tag_uids: list[str],
    db: AsyncSession,
) -> None:
    """整批替換 entity 的 tag 綁定。

    取現有 alive row 集合, diff 出：
    - add：要新增的 tag_uid → 既無 row 則 create，已軟刪則復活
    - remove：要移除的 tag_uid → 直接 soft_delete

    Caller 須在更外層 transaction 內呼叫；本函式只 `await db.flush()`。
    """
    target_set: set[uuid.UUID] = {uuid.UUID(u) for u in target_tag_uids}
    entity_uuid = uuid.UUID(entity_uid)

    current_stmt = select(EntityTag).where(
        EntityTag.entity_type == entity_type,
        EntityTag.entity_uid == entity_uuid,
        EntityTag.is_deleted == False,  # noqa: E712
    )
    current_rows = (await db.execute(current_stmt)).scalars().all()
    current_map = {row.tag_uid: row for row in current_rows}
    current_set = set(current_map.keys())

    to_remove = current_set - target_set
    to_add = target_set - current_set

    for tag_uid in to_remove:
        current_map[tag_uid].is_deleted = True

    for tag_uid in to_add:
        existing = await _get_existing_assignment(
            tag_uid, entity_type, entity_uuid, db
        )
        if existing is None:
            db.add(
                EntityTag(
                    tag_uid=tag_uid,
                    entity_type=entity_type,
                    entity_uid=entity_uuid,
                )
            )
        else:
            existing.is_deleted = False
            existing.is_active = True

    await db.flush()


async def soft_delete_by_tag(tag_uid: str, db: AsyncSession) -> int:
    """軟刪 tag 時連動把所有對應 entity_tag row 軟刪。回傳影響筆數。"""
    stmt = (
        update(EntityTag)
        .where(
            EntityTag.tag_uid == uuid.UUID(tag_uid),
            EntityTag.is_deleted == False,  # noqa: E712
        )
        .values(is_deleted=True)
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount or 0


def apply_tag_filter(
    stmt: Select,
    entity_type: str,
    entity_uid_column,
    tag_uids: list[str] | None,
) -> Select:
    """AND filter：要求 entity 同時掛有 `tag_uids` 內所有 tag。

    用「非相關性 IN 子查詢」實作（不依賴 SA `correlate_except` 推斷），
    產出 SQL：

        WHERE <entity_uid_column> IN (
            SELECT entity_uid FROM entity_tag
            WHERE entity_type = :type
              AND tag_uid IN (:tag_uids)
              AND is_deleted = FALSE
            GROUP BY entity_uid
            HAVING COUNT(DISTINCT tag_uid) = :n
        )

    `entity_uid_column` 為對應 entity 表的 UID 欄位（例 `Skill.skill_uid`）；
    空 list / None → 不加 filter；無效 UUID 由呼叫端事先過濾。
    """
    if not tag_uids:
        return stmt

    tag_uuids = [uuid.UUID(u) for u in tag_uids]
    n = len(set(tag_uuids))

    inner = (
        select(EntityTag.entity_uid)
        .where(
            EntityTag.entity_type == entity_type,
            EntityTag.tag_uid.in_(tag_uuids),
            EntityTag.is_deleted == False,  # noqa: E712
        )
        .group_by(EntityTag.entity_uid)
        .having(func.count(func.distinct(EntityTag.tag_uid)) == n)
    )
    return stmt.where(entity_uid_column.in_(inner))


__all__ = [
    "list_alive_by_entity",
    "get_tags_bulk",
    "set_entity_tags",
    "soft_delete_by_tag",
    "apply_tag_filter",
]
