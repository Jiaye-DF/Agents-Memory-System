"""收藏 / 取消收藏 / 我的收藏列表 Service。

關鍵設計（docs/Tasks/v1.2/tasks-v1.2.1.md §3-1 / propose §2-1）：
- 同 transaction 內寫 `user_favorite` 與 UPDATE 對應資源表的 `favorite_count`
- idempotent：重複 POST / DELETE 不會重複 +/- 計數
- tombstone：來源資源被軟刪 / 遺失 → 列表仍回該收藏項，resource=null + tombstone_reason="resource_removed"
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ensure_readable
from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.models.user_favorite import UserFavorite
from app.repositories import (
    agent_repository,
    script_repository,
    skill_repository,
    user_favorite_repository,
)

# 與 V34 CHECK 對齊；script 於 v1.2.3 才導入但提前列入白名單
ALLOWED_RESOURCE_TYPES = {"agent", "skill", "script"}


def _validate_resource_type(resource_type: str) -> None:
    if resource_type not in ALLOWED_RESOURCE_TYPES:
        raise AppError(
            detail=f"不支援的資源類型：{resource_type}",
            response_code=400,
            status_code=400,
        )


def _validate_uid_format(resource_uid: str) -> None:
    try:
        uuid.UUID(resource_uid)
    except (ValueError, AttributeError, TypeError) as exc:
        raise AppError(
            detail="資源 UID 格式無效",
            response_code=400,
            status_code=400,
        ) from exc


async def _dispatch_count_update(
    resource_type: str, resource_uid: str, delta: int, db: AsyncSession
) -> int | None:
    """依資源類型把 `favorite_count += delta` 路由到對應表。"""
    if resource_type == "agent":
        return await agent_repository.increment_favorite_count(
            resource_uid, delta, db
        )
    if resource_type == "skill":
        return await skill_repository.increment_favorite_count(
            resource_uid, delta, db
        )
    if resource_type == "script":
        return await script_repository.increment_favorite_count(
            resource_uid, delta, db
        )
    raise AppError(
        detail=f"不支援的資源類型：{resource_type}",
        response_code=400,
        status_code=400,
    )


async def _ensure_resource_readable(
    resource_type: str,
    resource_uid: str,
    user_uid: str,
    role: str,
    db: AsyncSession,
) -> None:
    """收藏動作前校驗資源存在 + 使用者可讀（擁有或公開或 admin）。"""
    if resource_type == "agent":
        agent = await agent_repository.get_by_uid(resource_uid, db)
        ensure_readable(agent, user_uid, role, "找不到指定的 Agent")
        return
    if resource_type == "skill":
        skill = await skill_repository.get_by_uid(resource_uid, db)
        ensure_readable(skill, user_uid, role, "找不到指定的 Skill")
        return
    if resource_type == "script":
        script = await script_repository.get_by_uid(resource_uid, db)
        # v1.2 Script 無 visibility 概念，僅擁有者 / admin 可讀
        if script is None:
            raise AppError(
                detail="找不到指定的 Script",
                response_code=404,
                status_code=404,
            )
        if role != "admin" and str(script.owner_user_uid) != user_uid:
            raise AppError(
                detail="找不到指定的 Script",
                response_code=404,
                status_code=404,
            )
        return
    raise AppError(
        detail=f"不支援的資源類型：{resource_type}",
        response_code=400,
        status_code=400,
    )


async def add_favorite(
    user_uid: str,
    role: str,
    resource_type: str,
    resource_uid: str,
    db: AsyncSession,
) -> dict:
    """新增 / 復活收藏。idempotent：已收藏時不重複 +1。"""
    _validate_resource_type(resource_type)
    _validate_uid_format(resource_uid)
    await _ensure_resource_readable(
        resource_type, resource_uid, user_uid, role, db
    )

    _, changed = await user_favorite_repository.add(
        user_uid, resource_type, resource_uid, db
    )
    if changed:
        new_count = await _dispatch_count_update(
            resource_type, resource_uid, 1, db
        )
    else:
        # 未改動計數：用讀取方式取得當前值
        new_count = await _get_current_favorite_count(
            resource_type, resource_uid, db
        )

    return {
        "favorited": True,
        "favorite_count": new_count or 0,
    }


async def remove_favorite(
    user_uid: str,
    resource_type: str,
    resource_uid: str,
    db: AsyncSession,
) -> dict:
    """軟刪收藏。idempotent：未收藏時不重複 -1（也不會讓計數變負）。"""
    _validate_resource_type(resource_type)
    _validate_uid_format(resource_uid)

    removed = await user_favorite_repository.remove(
        user_uid, resource_type, resource_uid, db
    )
    if removed:
        new_count = await _dispatch_count_update(
            resource_type, resource_uid, -1, db
        )
    else:
        new_count = await _get_current_favorite_count(
            resource_type, resource_uid, db
        )

    return {
        "favorited": False,
        "favorite_count": new_count or 0,
    }


async def _get_current_favorite_count(
    resource_type: str, resource_uid: str, db: AsyncSession
) -> int | None:
    if resource_type == "agent":
        agent = await agent_repository.get_by_uid(resource_uid, db)
        return agent.favorite_count if agent else None
    if resource_type == "skill":
        skill = await skill_repository.get_by_uid(resource_uid, db)
        return skill.favorite_count if skill else None
    if resource_type == "script":
        script = await script_repository.get_by_uid(resource_uid, db)
        return script.favorite_count if script else None
    return None


def _agent_snapshot(agent) -> dict:
    return {
        "uid": str(agent.agent_uid),
        "name": agent.name,
        "description": agent.description,
        "owner_uid": str(agent.owner_uid),
        "owner_username": agent.owner.username if agent.owner else None,
        "visibility": agent.visibility,
        "favorite_count": agent.favorite_count,
        "download_count": agent.download_count,
        "created_at": to_taipei_iso(agent.created_at),
        "updated_at": to_taipei_iso(agent.updated_at),
    }


def _skill_snapshot(skill) -> dict:
    return {
        "uid": str(skill.skill_uid),
        "name": skill.name,
        "description": skill.description,
        "owner_uid": str(skill.owner_uid),
        "owner_username": skill.owner.username if skill.owner else None,
        "visibility": skill.visibility,
        "favorite_count": skill.favorite_count,
        "download_count": skill.download_count,
        "created_at": to_taipei_iso(skill.created_at),
        "updated_at": to_taipei_iso(skill.updated_at),
    }


def _script_snapshot(script) -> dict:
    return {
        "uid": str(script.script_uid),
        "name": script.name,
        "description": script.description,
        "owner_uid": str(script.owner_user_uid),
        "owner_username": script.owner.username if script.owner else None,
        # v1.2 Script 無 visibility 概念
        "visibility": None,
        "favorite_count": script.favorite_count,
        "download_count": script.download_count,
        "created_at": to_taipei_iso(script.created_at),
        "updated_at": to_taipei_iso(script.updated_at),
    }


async def _build_snapshot_map(
    favs: list[UserFavorite],
    resource_type: str,
    db: AsyncSession,
) -> dict[str, dict]:
    """依型別批次撈出資源並回傳 {uid: snapshot}；軟刪 / 不存在的 uid 不會出現在 map 中（→ tombstone）。"""
    uids = [
        str(f.resource_uid) for f in favs if f.resource_type == resource_type
    ]
    if not uids:
        return {}

    if resource_type == "agent":
        rows = await agent_repository.get_by_uids(uids, db)
        return {str(r.agent_uid): _agent_snapshot(r) for r in rows}
    if resource_type == "skill":
        rows = await skill_repository.get_by_uids(uids, db)
        return {str(r.skill_uid): _skill_snapshot(r) for r in rows}
    if resource_type == "script":
        rows = await script_repository.get_by_uids(uids, db)
        return {str(r.script_uid): _script_snapshot(r) for r in rows}
    return {}


async def list_my_favorites(
    user_uid: str,
    resource_type: str | None,
    page: int,
    size: int,
    db: AsyncSession,
) -> dict:
    """列出使用者的收藏。資源已被軟刪 / 不存在 → tombstone。"""
    if resource_type is not None:
        _validate_resource_type(resource_type)

    favs, total = await user_favorite_repository.list_by_owner(
        user_uid, resource_type, page, size, db
    )

    snap_maps = {
        rt: await _build_snapshot_map(favs, rt, db)
        for rt in ("agent", "skill", "script")
    }

    items: list[dict] = []
    for f in favs:
        snap = snap_maps[f.resource_type].get(str(f.resource_uid))
        items.append(
            {
                "user_favorite_uid": str(f.user_favorite_uid),
                "resource_type": f.resource_type,
                "resource_uid": str(f.resource_uid),
                "resource": snap,
                "tombstone_reason": None if snap else "resource_removed",
                "created_at": to_taipei_iso(f.created_at),
            }
        )

    return {
        "items": items,
        "page": page,
        "size": size,
        "total": total,
    }
