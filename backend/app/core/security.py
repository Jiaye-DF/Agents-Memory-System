from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"

# SSO 使用者 refresh_token TTL：對齊中央 SSO JWT (24h)。本地帳密走 settings.REFRESH_TOKEN_EXPIRE_DAYS。
# 動機：SSO 使用者在 Azure AD 被停用後, 本地若給 7 天 TTL 等於開後門, 縮成 24h 把暴露窗口壓到中央 token 生命週期內。
SSO_REFRESH_TOKEN_EXPIRE_HOURS = 24


def create_access_token(
    user_uid: str, role: str, username: str, auth_method: str = "local"
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "user_uid": user_uid,
        "role": role,
        "username": username,
        "exp": expire,
        "iat": now,
        "type": "access",
        "auth_method": auth_method,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    user_uid: str, role: str, username: str, auth_method: str = "local"
) -> str:
    now = datetime.now(timezone.utc)
    if auth_method == "sso":
        expire = now + timedelta(hours=SSO_REFRESH_TOKEN_EXPIRE_HOURS)
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "user_uid": user_uid,
        "role": role,
        "username": username,
        "exp": expire,
        "iat": now,
        "type": "refresh",
        "auth_method": auth_method,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
