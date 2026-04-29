from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.clients import sso_client
from app.core.config import settings
from app.core.response import failure, success
from app.schemas.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SsoBackChannelLogoutRequest,
    SsoExchangeRequest,
    TokenPayload,
)
from app.schemas.response import ApiResponse, MessageData, TokenData
from app.services import auth_service, sso_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_KEY = "refresh_token"
COOKIE_PATH = "/api/v1/auth"
COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
COOKIE_SECURE = settings.APP_ENV == "production"


def _set_refresh_cookie(response: JSONResponse, refresh_token: str) -> None:
    response.set_cookie(
        key=COOKIE_KEY,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path=COOKIE_PATH,
        max_age=COOKIE_MAX_AGE,
    )


def _delete_refresh_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        key=COOKIE_KEY,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path=COOKIE_PATH,
    )


@router.post("/register", response_model=ApiResponse[MessageData])
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await auth_service.register(data, db)
    return success(data=result, response_code=201)


@router.post("/login", response_model=ApiResponse[TokenData])
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    access_token, refresh_token = await auth_service.login(data, db)
    response = success(
        data={"access_token": access_token, "token_type": "bearer"}
    )
    _set_refresh_cookie(response, refresh_token)
    return response


@router.post("/logout", response_model=ApiResponse[MessageData])
async def logout(
    current_user: TokenPayload = Depends(get_current_user),
    refresh_token: str | None = Cookie(None, alias=COOKIE_KEY),
) -> JSONResponse:
    # SSO 用戶：走 SSO logout 通知中央 + 清 SSO 綁定；同時 blacklist refresh
    # 非 SSO 用戶：走原本 local logout
    if settings.SSO_URL:
        await sso_auth_service.logout(current_user.user_uid, refresh_token)
    elif refresh_token is not None:
        await auth_service.logout(refresh_token)
    response = success(data={"message": "已登出"})
    _delete_refresh_cookie(response)
    return response


@router.post("/refresh", response_model=ApiResponse[TokenData])
async def refresh(
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(None, alias=COOKIE_KEY),
) -> JSONResponse:
    if refresh_token is None:
        return failure(detail="無效的 Token", response_code=401, status_code=401)
    new_access_token, new_refresh_token = await auth_service.refresh(
        refresh_token, db
    )
    response = success(
        data={"access_token": new_access_token, "token_type": "bearer"}
    )
    _set_refresh_cookie(response, new_refresh_token)
    return response


@router.post("/reset-password", response_model=ApiResponse[MessageData])
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await auth_service.reset_password(data, db)
    return success(data={"message": "密碼重設成功"})


# === DF-SSO 橋接 endpoints ===
# 對應 DF-SSO INTEGRATION.md。Frontend Next.js 收到 SSO 回 callback 後把 code POST 給此處，
# 後端做中央 exchange + /me + upsert user，最後回本系統 local JWT（重用既有 cookie 機制）。


@router.post("/sso/exchange", response_model=ApiResponse[TokenData])
async def sso_exchange(
    data: SsoExchangeRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        access_token, refresh_token = await sso_auth_service.exchange_and_login(
            data.code, db
        )
    except sso_client.SsoClientError as exc:
        status = 401 if exc.code in {"exchange_failed", "session_expired"} else 502
        return failure(detail=exc.code, response_code=status, status_code=status)

    response = success(
        data={"access_token": access_token, "token_type": "bearer"}
    )
    _set_refresh_cookie(response, refresh_token)
    return response


@router.post("/sso/logout", response_model=ApiResponse[MessageData])
async def sso_logout(
    current_user: TokenPayload = Depends(get_current_user),
    refresh_token: str | None = Cookie(None, alias=COOKIE_KEY),
) -> JSONResponse:
    redirect = await sso_auth_service.logout(current_user.user_uid, refresh_token)
    response = success(data={"message": redirect})
    _delete_refresh_cookie(response)
    return response


@router.post("/sso/back-channel-logout", response_model=ApiResponse[MessageData])
async def sso_back_channel_logout(
    data: SsoBackChannelLogoutRequest,
) -> JSONResponse:
    """中央 SSO 撤銷 session 時的 webhook（HMAC 驗證）。"""
    await sso_auth_service.handle_back_channel_logout(
        data.user_id, data.timestamp, data.signature
    )
    return success(data={"message": "ok"})


@router.get("/sso/authorize-url", response_model=ApiResponse[MessageData])
async def sso_authorize_url() -> JSONResponse:
    """提供前端登入按鈕用的 authorize URL（避免 NEXT_PUBLIC_* 出現 build-time 寫死）。"""
    url = sso_auth_service.authorize_url()
    if not url:
        return failure(detail="sso_not_configured", response_code=503, status_code=503)
    return success(data={"message": url})
