import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.repositories import user_repository
from app.schemas.auth.schemas import LoginRequest, RegisterRequest, ResetPasswordRequest

logger = logging.getLogger(__name__)

BLACKLIST_PREFIX = "token:blacklist:"


async def register(data: RegisterRequest, db: AsyncSession) -> dict:
    existing = await user_repository.get_by_account(data.account, db)
    if existing is not None:
        raise AppError(detail="此帳號已被註冊", response_code=409, status_code=409)

    member_role = await user_repository.get_role_by_name("member", db)
    if member_role is None:
        raise AppError(
            detail="系統設定錯誤，請聯繫管理員",
            response_code=500,
            status_code=500,
        )

    hashed = hash_password(data.password)
    user = await user_repository.create(
        {
            "username": data.username,
            "account": data.account,
            "hashed_password": hashed,
            "role_uid": member_role.user_role_uid,
        },
        db,
    )
    return {"user_uid": str(user.user_uid)}


async def login(data: LoginRequest, db: AsyncSession) -> tuple[str, str]:
    user = await user_repository.get_by_account(data.account, db)

    if user is None:
        raise AppError(detail="帳號或密碼錯誤", response_code=401, status_code=401)

    if not user.is_active:
        raise AppError(
            detail="帳號已被鎖定，請聯繫管理員",
            response_code=403,
            status_code=403,
        )

    now = datetime.now(timezone.utc)
    if user.locked_until is not None and user.locked_until > now:
        raise AppError(
            detail="帳號已被鎖定，請稍後再試",
            response_code=403,
            status_code=403,
        )

    if not verify_password(data.password, user.hashed_password):
        user.login_fail_count += 1
        fail_count = user.login_fail_count

        update_data: dict = {"login_fail_count": fail_count}

        if fail_count >= 15:
            update_data["is_active"] = False
        elif fail_count >= 10:
            update_data["locked_until"] = now + timedelta(hours=1)
        elif fail_count >= 5:
            update_data["locked_until"] = now + timedelta(minutes=15)

        await user_repository.update(user, update_data, db)
        raise AppError(detail="帳號或密碼錯誤", response_code=401, status_code=401)

    await user_repository.update(
        user,
        {"login_fail_count": 0, "locked_until": None},
        db,
    )

    role_name = user.role.name
    access_token = create_access_token(str(user.user_uid), role_name)
    refresh_token = create_refresh_token(str(user.user_uid), role_name)

    return access_token, refresh_token


async def logout(refresh_token: str) -> None:
    payload = verify_token(refresh_token)
    if payload is None:
        return

    exp = payload.get("exp")
    if exp is not None:
        now = datetime.now(timezone.utc).timestamp()
        ttl = int(exp - now)
        if ttl > 0:
            redis = get_redis()
            await redis.setex(f"{BLACKLIST_PREFIX}{refresh_token}", ttl, "1")


async def refresh(refresh_token: str, db: AsyncSession) -> tuple[str, str]:
    payload = verify_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise AppError(detail="無效的 Token", response_code=401, status_code=401)

    redis = get_redis()
    is_blacklisted = await redis.get(f"{BLACKLIST_PREFIX}{refresh_token}")
    if is_blacklisted is not None:
        raise AppError(detail="無效的 Token", response_code=401, status_code=401)

    user_uid = payload.get("user_uid")
    if user_uid is None:
        raise AppError(detail="無效的 Token", response_code=401, status_code=401)

    user = await user_repository.get_by_uid(user_uid, db)
    if user is None or not user.is_active:
        raise AppError(detail="無效的 Token", response_code=401, status_code=401)

    role_name = user.role.name
    new_access_token = create_access_token(str(user.user_uid), role_name)
    new_refresh_token = create_refresh_token(str(user.user_uid), role_name)

    exp = payload.get("exp")
    if exp is not None:
        now = datetime.now(timezone.utc).timestamp()
        ttl = int(exp - now)
        if ttl > 0:
            await redis.setex(f"{BLACKLIST_PREFIX}{refresh_token}", ttl, "1")

    return new_access_token, new_refresh_token


async def reset_password(data: ResetPasswordRequest, db: AsyncSession) -> None:
    user = await user_repository.get_by_account_and_username(
        data.account, data.username, db
    )
    if user is None:
        raise AppError(
            detail="帳號或使用者名稱錯誤",
            response_code=400,
            status_code=400,
        )

    hashed = hash_password(data.new_password)
    await user_repository.update(user, {"hashed_password": hashed}, db)
