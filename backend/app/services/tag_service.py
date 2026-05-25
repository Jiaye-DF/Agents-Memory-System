"""Tag 業務邏輯。

權限模型：per-user owned。所有寫入操作必須是 owner（admin 亦無特權）。
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.models.tag import Tag
from app.repositories import entity_tag_repository, tag_repository

NOT_FOUND_DETAIL = "找不到指定的 Tag"


def _tag_to_summary(tag: Tag) -> dict:
    return {"tag_uid": str(tag.tag_uid), "name": tag.name}


def _tag_to_detail(tag: Tag, usage_count: int = 0) -> dict:
    return {
        "tag_uid": str(tag.tag_uid),
        "name": tag.name,
        "usage_count": usage_count,
        "created_at": to_taipei_iso(tag.created_at) or "",
    }


async def list_tags(
    user_uid: str, q: str | None, db: AsyncSession
) -> dict:
    rows = await tag_repository.list_by_owner(user_uid, q, db)
    return {
        "items": [_tag_to_detail(tag, count) for tag, count in rows],
    }


async def find_or_create_tag(
    user_uid: str, name: str, db: AsyncSession
) -> tuple[Tag, bool]:
    """Find-or-create：依 case-insensitive 名稱比對。

    回傳 `(tag, created)`：
    - 不存在 → create, created=True
    - 存在且未軟刪 → 直接回傳, created=False
    - 存在但已軟刪 → 復活, created=True

    並行寫入安全：兩個請求同名同時走 create → partial unique 索引擋下
    第二筆。用 SAVEPOINT 隔離 INSERT，IntegrityError 時回頭 refetch；
    外層 transaction 不受影響。
    """
    existing = await tag_repository.get_by_owner_name_any(user_uid, name, db)
    if existing is not None:
        if existing.is_deleted:
            return await tag_repository.revive(existing, db), True
        return existing, False

    try:
        async with db.begin_nested():
            tag = await tag_repository.create(user_uid, name, db)
        return tag, True
    except IntegrityError:
        # 並行同名 INSERT 撞唯一索引 → SAVEPOINT 已自動 rollback；回頭撈剛被別人寫進來那筆
        refetched = await tag_repository.get_by_owner_name_any(
            user_uid, name, db
        )
        if refetched is None:
            # 理論上不會到這（撞唯一索引代表必有同名 row）；防禦性 raise
            raise
        if refetched.is_deleted:
            return await tag_repository.revive(refetched, db), True
        return refetched, False


async def rename_tag(
    tag_uid: str, user_uid: str, new_name: str, db: AsyncSession
) -> Tag:
    tag = await tag_repository.get_by_uid(tag_uid, db)
    if tag is None:
        raise AppError(
            detail=NOT_FOUND_DETAIL, response_code=404, status_code=404
        )
    if str(tag.owner_user_uid) != user_uid:
        raise AppError(
            detail="權限不足", response_code=403, status_code=403
        )

    # case-insensitive 衝突檢查：與 partial unique 索引一致
    conflict = await tag_repository.get_by_owner_name_any(
        user_uid, new_name, db
    )
    if (
        conflict is not None
        and not conflict.is_deleted
        and conflict.tag_uid != tag.tag_uid
    ):
        raise AppError(
            detail="已有同名 Tag 存在", response_code=409, status_code=409
        )

    return await tag_repository.rename(tag, new_name, db)


async def delete_tag(
    tag_uid: str, user_uid: str, db: AsyncSession
) -> None:
    """軟刪 tag + 連動 entity_tag 軟刪。同一 DB session, 由外層 commit 保證原子性。"""
    tag = await tag_repository.get_by_uid(tag_uid, db)
    if tag is None:
        raise AppError(
            detail=NOT_FOUND_DETAIL, response_code=404, status_code=404
        )
    if str(tag.owner_user_uid) != user_uid:
        raise AppError(
            detail="權限不足", response_code=403, status_code=403
        )

    await tag_repository.soft_delete(tag, db)
    await entity_tag_repository.soft_delete_by_tag(tag_uid, db)


async def resolve_tag_uids(
    user_uid: str,
    names: list[str] | None,
    tag_uids: list[str] | None,
    db: AsyncSession,
) -> list[str]:
    """把 EntityTagsRequest 的兩種 input 解析為 tag_uid 字串列表。

    - `names` 走 find-or-create（每個 name → 對應 tag_uid）
    - `tag_uids` 直接驗證存在且為當前 user owner

    上層已 `model_validator` 確保二選一互斥, 此函式不再檢查。
    """
    if names is not None:
        result: list[str] = []
        for name in names:
            tag, _ = await find_or_create_tag(user_uid, name, db)
            result.append(str(tag.tag_uid))
        return result

    assert tag_uids is not None
    if not tag_uids:
        return []

    tags = await tag_repository.get_by_uids(tag_uids, db)
    if len(tags) != len(set(tag_uids)):
        raise AppError(
            detail="部分 tag_uid 不存在或已刪除",
            response_code=400,
            status_code=400,
        )
    for t in tags:
        if str(t.owner_user_uid) != user_uid:
            raise AppError(
                detail="僅能使用自己擁有的 Tag",
                response_code=403,
                status_code=403,
            )
    return [str(t.tag_uid) for t in tags]


# 公開 helper for entity services
def tag_to_summary(tag: Tag) -> dict:
    return _tag_to_summary(tag)


def tag_to_detail(tag: Tag, usage_count: int = 0) -> dict:
    return _tag_to_detail(tag, usage_count)
