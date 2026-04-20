from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.llm_model import LlmModel
from app.repositories import llm_model_repository
from app.schemas.models.schemas import (
    LlmModelCreateRequest,
    LlmModelUpdateRequest,
)
from app.services import openrouter_service

DEFAULT_PROVIDER = "OpenRouter"


def _to_dict(model: LlmModel) -> dict:
    return {
        "llm_model_uid": str(model.llm_model_uid),
        "provider": model.provider,
        "model_id": model.model_id,
        "display_name": model.display_name,
        "is_active": model.is_active,
        "is_deleted": model.is_deleted,
        "created_at": model.created_at.isoformat(),
        "updated_at": model.updated_at.isoformat(),
    }


async def list_models_admin(
    cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    decoded_cursor: int | None = None
    if cursor is not None:
        decoded_cursor = decode_cursor(cursor)

    rows = await llm_model_repository.list_all(decoded_cursor, limit, db)

    has_next = len(rows) > limit
    items = rows[:limit]

    next_cursor: str | None = None
    if has_next and items:
        next_cursor = encode_cursor(items[-1].pid)

    return {
        "items": [_to_dict(m) for m in items],
        "next_cursor": next_cursor,
        "has_next": has_next,
    }


async def create_model(data: LlmModelCreateRequest, db: AsyncSession) -> dict:
    existing = await llm_model_repository.get_by_model_id(data.model_id, db)
    if existing is not None:
        raise AppError(
            detail="模型 ID 已存在", response_code=409, status_code=409
        )

    await openrouter_service.verify_model_id(data.model_id)

    model = await llm_model_repository.create(
        {
            "provider": DEFAULT_PROVIDER,
            "model_id": data.model_id,
            "display_name": data.display_name,
        },
        db,
    )
    return _to_dict(model)


async def get_model(llm_model_uid: str, db: AsyncSession) -> dict:
    model = await llm_model_repository.get_by_uid(llm_model_uid, db)
    if model is None:
        raise AppError(
            detail="找不到指定的模型", response_code=404, status_code=404
        )
    return _to_dict(model)


async def update_model(
    llm_model_uid: str, data: LlmModelUpdateRequest, db: AsyncSession
) -> dict:
    model = await llm_model_repository.get_by_uid(llm_model_uid, db)
    if model is None:
        raise AppError(
            detail="找不到指定的模型", response_code=404, status_code=404
        )

    update_data: dict = {}
    if data.display_name is not None:
        update_data["display_name"] = data.display_name
    if data.is_active is not None:
        update_data["is_active"] = data.is_active

    if not update_data:
        raise AppError(
            detail="未提供任何更新欄位", response_code=400, status_code=400
        )

    await llm_model_repository.update(model, update_data, db)
    return _to_dict(model)


async def delete_model(llm_model_uid: str, db: AsyncSession) -> None:
    model = await llm_model_repository.get_by_uid(llm_model_uid, db)
    if model is None:
        raise AppError(
            detail="找不到指定的模型", response_code=404, status_code=404
        )
    await llm_model_repository.soft_delete(model, db)
