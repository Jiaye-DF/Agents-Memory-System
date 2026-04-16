from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.user import User
from app.repositories import user_repository
from app.schemas.admin.schemas import UserUpdateRequest


def _user_to_dict(user: User) -> dict:
    return {
        "user_uid": str(user.user_uid),
        "username": user.username,
        "account": user.account,
        "role_name": user.role.name,
        "is_active": user.is_active,
        "login_fail_count": user.login_fail_count,
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "created_at": user.created_at.isoformat(),
    }


async def list_users(
    cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    decoded_cursor: int | None = None
    if cursor is not None:
        decoded_cursor = decode_cursor(cursor)

    rows = await user_repository.list_users(decoded_cursor, limit, db)

    has_next = len(rows) > limit
    items = rows[:limit]

    next_cursor: str | None = None
    if has_next and items:
        next_cursor = encode_cursor(items[-1].pid)

    return {
        "items": [_user_to_dict(u) for u in items],
        "next_cursor": next_cursor,
        "has_next": has_next,
    }


async def get_user(user_uid: str, db: AsyncSession) -> dict:
    user = await user_repository.get_by_uid(user_uid, db)
    if user is None:
        raise AppError(detail="找不到指定的使用者", response_code=404, status_code=404)
    return _user_to_dict(user)


async def update_user(
    user_uid: str, data: UserUpdateRequest, db: AsyncSession
) -> dict:
    user = await user_repository.get_by_uid(user_uid, db)
    if user is None:
        raise AppError(detail="找不到指定的使用者", response_code=404, status_code=404)

    update_data: dict = {}

    if data.role_uid is not None:
        role = await user_repository.get_role_by_uid(data.role_uid, db)
        if role is None:
            raise AppError(
                detail="指定的角色不存在", response_code=400, status_code=400
            )
        update_data["role_uid"] = role.user_role_uid

    if data.unlock is True:
        update_data["login_fail_count"] = 0
        update_data["locked_until"] = None
        update_data["is_active"] = True

    if not update_data:
        raise AppError(detail="未提供任何更新欄位", response_code=400, status_code=400)

    await user_repository.update(user, update_data, db)
    return _user_to_dict(user)


async def list_roles(db: AsyncSession) -> dict:
    roles = await user_repository.list_roles(db)
    return {
        "roles": [
            {
                "user_role_uid": str(r.user_role_uid),
                "name": r.name,
                "description": r.description,
            }
            for r in roles
        ]
    }
