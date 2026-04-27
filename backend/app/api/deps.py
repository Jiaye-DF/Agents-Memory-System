from collections.abc import AsyncIterator

from fastapi import Depends, params
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import AppError
from app.core.logging_config import set_user_uid
from app.core.security import verify_token
from app.schemas.auth.schemas import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> TokenPayload:
    payload = verify_token(token)
    if payload is None or payload.get("type") != "access":
        raise AppError(detail="認證失敗", response_code=401, status_code=401)

    user_uid = payload.get("user_uid")
    role = payload.get("role")

    if user_uid is None or role is None:
        raise AppError(detail="認證失敗", response_code=401, status_code=401)

    set_user_uid(user_uid)
    return TokenPayload(user_uid=user_uid, role=role)


def get_current_user_from_query(token: str) -> TokenPayload:
    """SSE 等不支援自訂 header 的場景：以 query string token 驗證。

    與 `get_current_user` 共用底層 `verify_token`，但不依賴 OAuth2 Bearer header；
    僅供 EventSource 連線使用，不要套到一般 endpoint。
    """
    payload = verify_token(token)
    if payload is None or payload.get("type") != "access":
        raise AppError(detail="認證失敗", response_code=401, status_code=401)

    user_uid = payload.get("user_uid")
    role = payload.get("role")

    if user_uid is None or role is None:
        raise AppError(detail="認證失敗", response_code=401, status_code=401)

    return TokenPayload(user_uid=user_uid, role=role)


def require_role(*allowed_roles: str) -> params.Depends:
    async def checker(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if current_user.role not in allowed_roles:
            raise AppError(detail="權限不足", response_code=403, status_code=403)
        return current_user

    return Depends(checker)
