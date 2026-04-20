from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.agent_language import AgentLanguage
from app.repositories import agent_language_repository
from app.schemas.agent_languages.schemas import (
    AgentLanguageCreateRequest,
    AgentLanguageUpdateRequest,
)


def _to_dict(obj: AgentLanguage) -> dict:
    return {
        "agent_language_uid": str(obj.agent_language_uid),
        "code": obj.code,
        "name": obj.name,
        "sort_order": obj.sort_order,
        "is_default": obj.is_default,
        "is_active": obj.is_active,
        "created_at": to_taipei_iso(obj.created_at),
        "updated_at": to_taipei_iso(obj.updated_at),
    }


async def list_languages(db: AsyncSession) -> dict:
    rows = await agent_language_repository.list_active(db)
    return {"items": [_to_dict(r) for r in rows]}


async def list_languages_admin(
    cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    decoded_cursor: int | None = None
    if cursor is not None:
        decoded_cursor = decode_cursor(cursor)

    rows = await agent_language_repository.list_all(decoded_cursor, limit, db)

    has_next = len(rows) > limit
    items = rows[:limit]

    next_cursor: str | None = None
    if has_next and items:
        next_cursor = encode_cursor(items[-1].pid)

    return {
        "items": [_to_dict(r) for r in items],
        "next_cursor": next_cursor,
        "has_next": has_next,
    }


async def get_language(uid: str, db: AsyncSession) -> dict:
    obj = await agent_language_repository.get_by_uid(uid, db)
    if obj is None:
        raise AppError(
            detail="找不到指定的語言", response_code=404, status_code=404
        )
    return _to_dict(obj)


async def create_language(
    data: AgentLanguageCreateRequest, db: AsyncSession
) -> dict:
    existing = await agent_language_repository.get_by_code(data.code, db)
    if existing is not None:
        raise AppError(
            detail="語系碼已存在", response_code=409, status_code=409
        )

    if data.is_default:
        # 先清除其他項目的 is_default，再寫入新的 default
        await agent_language_repository.clear_default(db)

    obj = await agent_language_repository.create(
        {
            "code": data.code,
            "name": data.name,
            "sort_order": data.sort_order,
            "is_default": data.is_default,
        },
        db,
    )
    return _to_dict(obj)


async def update_language(
    uid: str, data: AgentLanguageUpdateRequest, db: AsyncSession
) -> dict:
    obj = await agent_language_repository.get_by_uid(uid, db)
    if obj is None:
        raise AppError(
            detail="找不到指定的語言", response_code=404, status_code=404
        )

    update_data: dict = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.sort_order is not None:
        update_data["sort_order"] = data.sort_order
    if data.is_active is not None:
        update_data["is_active"] = data.is_active

    if data.is_default is True and not obj.is_default:
        # 切換為 default，先清除其他項的 is_default
        await agent_language_repository.clear_default(db, except_pid=obj.pid)
        update_data["is_default"] = True
    elif data.is_default is False and obj.is_default:
        raise AppError(
            detail="系統至少需要一個預設語言，無法取消此語言的預設狀態",
            response_code=400,
            status_code=400,
        )

    if not update_data:
        raise AppError(
            detail="未提供任何更新欄位", response_code=400, status_code=400
        )

    await agent_language_repository.update_obj(obj, update_data, db)
    return _to_dict(obj)


async def delete_language(uid: str, db: AsyncSession) -> None:
    obj = await agent_language_repository.get_by_uid(uid, db)
    if obj is None:
        raise AppError(
            detail="找不到指定的語言", response_code=404, status_code=404
        )

    if obj.is_default:
        raise AppError(
            detail="無法刪除預設語言，請先將其他語言設為預設",
            response_code=400,
            status_code=400,
        )

    await agent_language_repository.soft_delete(obj, db)
