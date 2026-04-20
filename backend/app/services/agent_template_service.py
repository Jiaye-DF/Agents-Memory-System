from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.models.agent_template import AgentTemplate
from app.repositories import agent_template_repository
from app.schemas.agent_templates.schemas import (
    AgentTemplateCreateRequest,
    AgentTemplateUpdateRequest,
)

NOT_FOUND_DETAIL = "找不到指定的範本"


def _to_dict(obj: AgentTemplate) -> dict:
    return {
        "agent_template_uid": str(obj.agent_template_uid),
        "template_key": obj.template_key,
        "label": obj.label,
        "description": obj.description,
        "name": obj.name,
        "identity": obj.identity,
        "language": obj.language,
        "style": obj.style,
        "role_prompt": obj.role_prompt,
        "greeting": obj.greeting,
        "temperature": obj.temperature,
        "max_tokens": obj.max_tokens,
        "response_format": obj.response_format,
        "response_format_example": obj.response_format_example,
        "sort_order": obj.sort_order,
        "is_active": obj.is_active,
        "created_at": to_taipei_iso(obj.created_at),
        "updated_at": to_taipei_iso(obj.updated_at),
    }


async def list_templates(db: AsyncSession) -> dict:
    rows = await agent_template_repository.list_active(db)
    return {"items": [_to_dict(r) for r in rows]}


async def list_templates_admin(
    cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    page = await paginate(db, agent_template_repository.stmt_all(), cursor, limit)
    return {
        "items": [_to_dict(r) for r in page.items],
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def get_template(uid: str, db: AsyncSession) -> dict:
    obj = await agent_template_repository.get_by_uid(uid, db)
    if obj is None:
        raise AppError(detail=NOT_FOUND_DETAIL, response_code=404, status_code=404)
    return _to_dict(obj)


async def create_template(
    data: AgentTemplateCreateRequest, db: AsyncSession
) -> dict:
    existing = await agent_template_repository.get_by_key(data.template_key, db)
    if existing is not None:
        raise AppError(
            detail="範本識別碼已存在", response_code=409, status_code=409
        )

    obj = await agent_template_repository.create(
        {
            "template_key": data.template_key,
            "label": data.label,
            "description": data.description,
            "name": data.name,
            "identity": data.identity,
            "language": data.language,
            "style": data.style,
            "role_prompt": data.role_prompt,
            "greeting": data.greeting,
            "temperature": data.temperature,
            "max_tokens": data.max_tokens,
            "response_format": data.response_format,
            "response_format_example": data.response_format_example,
            "sort_order": data.sort_order,
        },
        db,
    )
    return _to_dict(obj)


async def update_template(
    uid: str, data: AgentTemplateUpdateRequest, db: AsyncSession
) -> dict:
    obj = await agent_template_repository.get_by_uid(uid, db)
    if obj is None:
        raise AppError(detail=NOT_FOUND_DETAIL, response_code=404, status_code=404)

    update_data: dict = {}
    for field in (
        "label",
        "description",
        "name",
        "identity",
        "language",
        "style",
        "role_prompt",
        "greeting",
        "temperature",
        "max_tokens",
        "response_format",
        "response_format_example",
        "sort_order",
        "is_active",
    ):
        value = getattr(data, field)
        if value is not None:
            update_data[field] = value

    if not update_data:
        raise AppError(
            detail="未提供任何更新欄位", response_code=400, status_code=400
        )

    await agent_template_repository.update_obj(obj, update_data, db)
    return _to_dict(obj)


async def delete_template(uid: str, db: AsyncSession) -> None:
    obj = await agent_template_repository.get_by_uid(uid, db)
    if obj is None:
        raise AppError(detail=NOT_FOUND_DETAIL, response_code=404, status_code=404)
    await agent_template_repository.soft_delete(obj, db)
