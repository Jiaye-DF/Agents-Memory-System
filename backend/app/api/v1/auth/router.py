from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.response import success, failure
from app.schemas.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPayload,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_KEY = "refresh_token"
COOKIE_PATH = "/api/v1/auth"
COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
COOKIE_SECURE = settings.CORS_ORIGINS != ["http://localhost:3000"]


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


@router.post("/register")
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await auth_service.register(data, db)
    return success(data=result, response_code=201)


@router.post("/login")
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


@router.post("/logout")
async def logout(
    _current_user: TokenPayload = Depends(get_current_user),
    refresh_token: str | None = Cookie(None, alias=COOKIE_KEY),
) -> JSONResponse:
    if refresh_token is not None:
        await auth_service.logout(refresh_token)
    response = success(data={"message": "已登出"})
    _delete_refresh_cookie(response)
    return response


@router.post("/refresh")
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


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await auth_service.reset_password(data, db)
    return success(data={"message": "密碼重設成功"})
