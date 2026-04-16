from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.core.response import success
from app.schemas.admin.schemas import UserUpdateRequest
from app.schemas.auth.schemas import TokenPayload
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    _current_user: TokenPayload = require_role("admin"),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.list_users(cursor, limit, db)
    return success(data=result)


@router.get("/users/{user_uid}")
async def get_user(
    user_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.get_user(user_uid, db)
    return success(data=result)


@router.put("/users/{user_uid}")
async def update_user(
    user_uid: str,
    data: UserUpdateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.update_user(user_uid, data, db)
    return success(data=result)


@router.get("/roles")
async def list_roles(
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.list_roles(db)
    return success(data=result)
