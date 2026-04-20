from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.core.response import success
from app.schemas.admin.schemas import UserUpdateRequest
from app.schemas.auth.schemas import TokenPayload
from app.schemas.models.schemas import (
    LlmModelCreateRequest,
    LlmModelUpdateRequest,
)
from app.services import admin_service, llm_model_service

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


@router.get("/llm-models")
async def list_llm_models(
    _current_user: TokenPayload = require_role("admin"),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await llm_model_service.list_models_admin(cursor, limit, db)
    return success(data=result)


@router.post("/llm-models")
async def create_llm_model(
    data: LlmModelCreateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await llm_model_service.create_model(data, db)
    return success(data=result, response_code=201)


@router.get("/llm-models/{llm_model_uid}")
async def get_llm_model(
    llm_model_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await llm_model_service.get_model(llm_model_uid, db)
    return success(data=result)


@router.put("/llm-models/{llm_model_uid}")
async def update_llm_model(
    llm_model_uid: str,
    data: LlmModelUpdateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await llm_model_service.update_model(llm_model_uid, data, db)
    return success(data=result)


@router.delete("/llm-models/{llm_model_uid}")
async def delete_llm_model(
    llm_model_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await llm_model_service.delete_model(llm_model_uid, db)
    return success(data={"message": "模型已刪除"})
