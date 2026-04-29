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
# SSO back-channel logout：撤銷某 user 在指定 timestamp 之前簽出的所有 token
SSO_LOGOUT_USER_PREFIX = "token:logout_user:"
# Single Logout 加強模式：剛被中央踢的使用者在這個 window 內回 401 會帶 X-Recently-Logged-Out
# header；前端據此跳 /?logged_out=1 而不是 silent re-auth, 讓「主動登出」視覺有效。
# spec 建議 5 分鐘：太短會讓使用者切到別 App 之前 cache 就過期；太長會阻礙重新登入。
RECENTLY_LOGGED_OUT_WINDOW_SECONDS = 300


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
    access_token = create_access_token(str(user.user_uid), role_name, user.username)
    refresh_token = create_refresh_token(str(user.user_uid), role_name, user.username)

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

    # SSO back-channel：若 token iat 早於該 user 的撤銷時間 → 立即失效
    logout_at = await redis.get(f"{SSO_LOGOUT_USER_PREFIX}{user_uid}")
    if logout_at is not None:
        iat = payload.get("iat")
        if iat is not None and int(iat) <= int(logout_at):
            # Single Logout 加強：在 window 內 → 帶 header, 前端跳 /?logged_out=1
            # 跨過 window → 不帶 header, 前端走 silent re-auth 嘗試恢復
            now_ts = datetime.now(timezone.utc).timestamp()
            is_recent = (
                int(now_ts) - int(logout_at) <= RECENTLY_LOGGED_OUT_WINDOW_SECONDS
            )
            raise AppError(
                detail="Session 已被中央登出",
                response_code=401,
                status_code=401,
                headers={"X-Recently-Logged-Out": "1"} if is_recent else None,
            )

    user = await user_repository.get_by_uid(user_uid, db)
    if user is None or not user.is_active:
        raise AppError(detail="無效的 Token", response_code=401, status_code=401)

    # SSO 使用者：每次 refresh 即時向中央驗證, 避免 Azure AD 停用後本地 7 天內仍能存取
    # 延遲 import 避開 sso_auth_service ↔ auth_service 潛在循環
    auth_method = payload.get("auth_method", "local")
    if auth_method == "sso":
        from app.services import sso_auth_service

        await sso_auth_service.verify_sso_session(user_uid)

    role_name = user.role.name
    new_access_token = create_access_token(
        str(user.user_uid), role_name, user.username, auth_method=auth_method
    )
    new_refresh_token = create_refresh_token(
        str(user.user_uid), role_name, user.username, auth_method=auth_method
    )

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
