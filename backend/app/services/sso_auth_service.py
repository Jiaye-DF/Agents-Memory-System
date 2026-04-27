"""DF-SSO 與本系統 local JWT 之間的橋接服務。

設計取捨：
- 中央發放 SSO JWT 給 frontend cookie，但本系統內部 API 仍使用既有 local JWT
  （access_token in memory + refresh_token httpOnly cookie），改動面最小。
- 登入：code → 中央 exchange → 中央 /me → upsert local user → 簽 local JWT。
- 登出：清 local refresh_token blacklist + 通知中央 Redis 刪 session。
- back-channel：中央踢人時，把該使用者所有 local refresh_token blacklist 起來，
  下次 frontend `/auth/refresh` 即 401。access_token 過期最多 ACCESS_TOKEN_EXPIRE_MINUTES。
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients import sso_client
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.redis import get_redis
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.user import User
from app.repositories import user_repository

logger = logging.getLogger(__name__)

# Redis keys
SSO_TOKEN_KEY = "sso:user_token:{user_uid}"  # local user_uid → SSO JWT（登出時用）
SSO_USERID_KEY = "sso:userid_to_uid:{sso_user_id}"  # SSO userId → local user_uid（back-channel 用）
SSO_TOKEN_TTL = 24 * 60 * 60  # 中央 JWT 24h，對齊
BLACKLIST_PREFIX = "token:blacklist:"
SSO_LOGOUT_USER_PREFIX = "token:logout_user:"  # value=timestamp，標記某 user 在此後簽的 token 全失效
SSO_LOGOUT_USER_TTL = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400

# back-channel HMAC 容忍的 timestamp 漂移（毫秒）
BACK_CHANNEL_MAX_DRIFT_MS = 30_000


async def exchange_and_login(
    code: str, db: AsyncSession
) -> tuple[str, str]:
    """code → 完成 SSO 流程並取得 local (access_token, refresh_token)。

    流程：
    1. 中央 /sso/exchange 換 SSO JWT
    2. 中央 /me 取得 user 資訊（即時驗證 + 拿 erpData / email）
    3. 以 email 為主鍵 upsert local user（沒 password，hashed_password 填亂數）
    4. 簽 local access/refresh token
    5. 把 SSO JWT 與 user_uid 綁定到 Redis，供登出與 back-channel 使用
    """
    # 1. exchange code
    exchange_data = await sso_client.exchange_code(code)
    sso_token: str = exchange_data["token"]

    # 2. 中央 /me
    sso_user = await sso_client.fetch_user(sso_token)
    sso_user_id = sso_user.get("userId")
    email = sso_user.get("email")
    name = sso_user.get("name") or email
    if not isinstance(sso_user_id, str) or not sso_user_id:
        raise AppError(detail="SSO 回傳缺少 userId", response_code=502, status_code=502)
    if not isinstance(email, str) or not email:
        raise AppError(detail="SSO 回傳缺少 email", response_code=502, status_code=502)

    # 3. upsert user（以 account=email 為唯一鍵）
    user = await _upsert_sso_user(email=email, name=name, db=db)

    if not user.is_active:
        raise AppError(
            detail="帳號已被鎖定，請聯繫管理員",
            response_code=403,
            status_code=403,
        )

    # 4. 簽 local token
    role_name = user.role.name
    access_token = create_access_token(str(user.user_uid), role_name, user.username)
    refresh_token = create_refresh_token(str(user.user_uid), role_name, user.username)

    # 5. Redis：SSO JWT 與 user_uid 綁定
    redis = get_redis()
    await redis.setex(
        SSO_TOKEN_KEY.format(user_uid=user.user_uid),
        SSO_TOKEN_TTL,
        sso_token,
    )
    await redis.setex(
        SSO_USERID_KEY.format(sso_user_id=sso_user_id),
        SSO_TOKEN_TTL,
        str(user.user_uid),
    )
    # 清掉先前可能殘留的「全使用者撤銷」標記，避免新 token 一發出就被 401
    await redis.delete(f"{SSO_LOGOUT_USER_PREFIX}{user.user_uid}")

    return access_token, refresh_token


async def _upsert_sso_user(email: str, name: str, db: AsyncSession) -> User:
    """以 email 為唯一鍵 upsert SSO user；不存在時自動建立 member 角色帳號。"""
    user = await user_repository.get_by_account(email, db)
    if user is not None:
        # 更新 username（SSO 端可能更名）
        if user.username != name:
            await user_repository.update(user, {"username": name}, db)
        return user

    member_role = await user_repository.get_role_by_name("member", db)
    if member_role is None:
        raise AppError(
            detail="系統未設定 member 角色，請聯繫管理員",
            response_code=500,
            status_code=500,
        )

    # SSO 使用者本機沒密碼，填一段亂數 bcrypt（保證永遠驗不過）
    random_password = secrets.token_urlsafe(48)
    hashed = hash_password(random_password)

    user = await user_repository.create(
        {
            "username": name,
            "account": email,
            "hashed_password": hashed,
            "role_uid": member_role.user_role_uid,
        },
        db,
    )
    # 重新撈一次帶 role 關聯
    user = await user_repository.get_by_uid(str(user.user_uid), db)
    assert user is not None
    return user


async def logout(user_uid: str, refresh_token: str | None) -> str:
    """通知中央刪 Redis session + blacklist local refresh_token。

    回傳中央驗證過的 redirect URL（fallback 為 APP_URL/?logged_out=1）。
    """
    fallback_redirect = f"{settings.APP_URL}/?logged_out=1"

    redis = get_redis()
    sso_token = await redis.get(SSO_TOKEN_KEY.format(user_uid=user_uid))
    final_redirect = fallback_redirect

    if sso_token:
        try:
            final_redirect = await sso_client.central_logout(
                sso_token, fallback_redirect
            )
        except sso_client.SsoClientError as exc:
            logger.warning("中央 logout 失敗：%s", exc)

    # blacklist refresh token + 清 SSO 綁定
    if refresh_token:
        await _blacklist_refresh_token(refresh_token)
    await redis.delete(SSO_TOKEN_KEY.format(user_uid=user_uid))
    return final_redirect


async def _blacklist_refresh_token(refresh_token: str) -> None:
    """以 TTL 對齊 token 到期時間的方式 blacklist。"""
    from app.core.security import verify_token

    payload = verify_token(refresh_token)
    if payload is None:
        return
    exp = payload.get("exp")
    if exp is None:
        return
    now = datetime.now(timezone.utc).timestamp()
    ttl = int(exp - now)
    if ttl <= 0:
        return
    redis = get_redis()
    await redis.setex(f"{BLACKLIST_PREFIX}{refresh_token}", ttl, "1")


async def handle_back_channel_logout(
    user_id: str, timestamp: int, signature: str
) -> None:
    """中央 back-channel logout：驗 HMAC + timestamp，撤銷該使用者所有 local session。

    撤銷策略：在 Redis 設 `token:logout_user:{user_uid}` = now，
    `auth_service.refresh` 會檢查 token iat < 此時間就視為失效。
    """
    if not settings.SSO_APP_SECRET:
        raise AppError(
            detail="sso_not_configured", response_code=503, status_code=503
        )

    # 1. timestamp 驗證（30s drift）
    now_ms = int(time.time() * 1000)
    if abs(now_ms - timestamp) > BACK_CHANNEL_MAX_DRIFT_MS:
        raise AppError(
            detail="Timestamp expired", response_code=401, status_code=401
        )

    # 2. HMAC 驗證（constant-time）
    expected = hmac.new(
        settings.SSO_APP_SECRET.encode(),
        f"{user_id}:{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise AppError(
            detail="Invalid signature", response_code=401, status_code=401
        )

    # 3. 找 SSO userId 對應的 local user_uid
    redis = get_redis()
    user_uid = await redis.get(SSO_USERID_KEY.format(sso_user_id=user_id))
    if not user_uid:
        # 沒登入過本系統，靜默成功
        return

    # 4. 撤銷該 user 所有 token
    await redis.setex(
        f"{SSO_LOGOUT_USER_PREFIX}{user_uid}",
        SSO_LOGOUT_USER_TTL,
        str(int(time.time())),
    )
    await redis.delete(SSO_TOKEN_KEY.format(user_uid=user_uid))
    await redis.delete(SSO_USERID_KEY.format(sso_user_id=user_id))


def authorize_url() -> str:
    """組登入頁要導去中央的 URL（給 frontend 拿來放 button href）。"""
    if not settings.SSO_URL or not settings.SSO_APP_ID or not settings.APP_URL:
        return ""
    redirect_uri = f"{settings.APP_URL}/api/auth/callback"
    from urllib.parse import quote

    return (
        f"{settings.SSO_URL}/api/auth/sso/authorize"
        f"?client_id={quote(settings.SSO_APP_ID)}"
        f"&redirect_uri={quote(redirect_uri)}"
    )
