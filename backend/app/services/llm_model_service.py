from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.models.llm_model import LlmModel
from app.repositories import llm_model_repository
from app.schemas.models.schemas import (
    LlmModelCreateRequest,
    LlmModelUpdateRequest,
)
from app.services import openrouter_service

DEFAULT_GATEWAY_PROVIDER = "OpenRouter"


def _derive_vendor(model_id: str) -> str:
    """從 model_id 第一段衍生廠商（anthropic / openai / google ...）。

    僅在新建模型寫入 DB 時使用；讀取時直接讀 llm_model.vendor 欄位。
    """
    head = (model_id or "").split("/", 1)[0].strip()
    return head or "openrouter"


def _to_dict(model: LlmModel) -> dict:
    return {
        "llm_model_uid": str(model.llm_model_uid),
        "provider": model.provider,
        "vendor": model.vendor,
        "model_id": model.model_id,
        "display_name": model.display_name,
        "is_active": model.is_active,
        "is_deleted": model.is_deleted,
        "is_default": model.is_default,
        "max_output_tokens": model.max_output_tokens,
        "created_at": to_taipei_iso(model.created_at),
        "updated_at": to_taipei_iso(model.updated_at),
    }


async def list_models_admin(
    cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    page = await paginate(db, llm_model_repository.stmt_all(), cursor, limit)
    return {
        "items": [_to_dict(m) for m in page.items],
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def create_model(data: LlmModelCreateRequest, db: AsyncSession) -> dict:
    existing = await llm_model_repository.get_by_model_id(data.model_id, db)
    if existing is not None:
        raise AppError(
            detail="模型 ID 已存在", response_code=409, status_code=409
        )

    await openrouter_service.verify_model_id(data.model_id)

    is_default = bool(data.is_default)
    if is_default:
        await llm_model_repository.clear_default(db)

    model = await llm_model_repository.create(
        {
            "provider": DEFAULT_GATEWAY_PROVIDER,
            "vendor": _derive_vendor(data.model_id),
            "model_id": data.model_id,
            "display_name": data.display_name,
            "is_default": is_default,
            "max_output_tokens": data.max_output_tokens,
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
    if data.max_output_tokens is not None:
        update_data["max_output_tokens"] = data.max_output_tokens

    if data.is_default is True and not model.is_default:
        await llm_model_repository.clear_default(db, except_pid=model.pid)
        update_data["is_default"] = True
    elif data.is_default is False and model.is_default:
        raise AppError(
            detail="系統至少需要一個預設模型，無法取消此模型的預設狀態",
            response_code=400,
            status_code=400,
        )

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

    if model.is_default:
        raise AppError(
            detail="無法刪除預設模型，請先將其他模型設為預設",
            response_code=400,
            status_code=400,
        )

    await llm_model_repository.soft_delete(model, db)
