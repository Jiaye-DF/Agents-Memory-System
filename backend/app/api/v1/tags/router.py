"""Tag 相關路由（per-user 自由輸入 tag 池）。

端點：
- GET    /api/v1/tags?q=             列出我的 tag（含 usage_count）
- POST   /api/v1/tags                Find-or-create
- PUT    /api/v1/tags/{tag_uid}      重新命名（衝突 409）
- DELETE /api/v1/tags/{tag_uid}      軟刪除 + 連動 entity_tag

Entity ↔ Tag 綁定的 endpoint（PUT /{entity}/{uid}/tags）位於各 entity router。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.auth.schemas import TokenPayload
from app.schemas.response import ApiResponse, MessageData
from app.schemas.tags.schemas import (
    TagCreateRequest,
    TagCreateResponse,
    TagDetail,
    TagListResponse,
    TagRenameRequest,
)
from app.services import tag_service

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=ApiResponse[TagListResponse])
async def list_tags(
    current_user: TokenPayload = Depends(get_current_user),
    q: str | None = Query(
        None,
        description="模糊搜尋 tag 名稱（case-insensitive）",
        max_length=50,
    ),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await tag_service.list_tags(current_user.user_uid, q, db)
    return success(data=result)


@router.post("", response_model=ApiResponse[TagCreateResponse])
async def create_tag(
    data: TagCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    tag, created = await tag_service.find_or_create_tag(
        current_user.user_uid, data.name, db
    )
    return success(
        data={
            "tag": tag_service.tag_to_detail(tag),
            "created": created,
        },
        response_code=201 if created else 200,
    )


@router.put("/{tag_uid}", response_model=ApiResponse[TagDetail])
async def rename_tag(
    tag_uid: str,
    data: TagRenameRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    tag = await tag_service.rename_tag(
        tag_uid, current_user.user_uid, data.name, db
    )
    return success(data=tag_service.tag_to_detail(tag))


@router.delete("/{tag_uid}", response_model=ApiResponse[MessageData])
async def delete_tag(
    tag_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await tag_service.delete_tag(tag_uid, current_user.user_uid, db)
    return success(data={"message": "Tag 已刪除"})
