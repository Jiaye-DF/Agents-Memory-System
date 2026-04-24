"""社群互動（收藏）相關路由。

規格（docs/Tasks/v1.2/tasks-v1.2.1.md §4-1）：
- POST   /api/v1/{agents|skills}/{uid}/favorite        → 新增 / 復活收藏
- DELETE /api/v1/{agents|skills}/{uid}/favorite        → 取消收藏
- GET    /api/v1/users/me/favorites?type=&page=&size=  → 我的收藏（支援 tombstone）

注意：此 router 與 agents_router / skills_router 共享前綴，不另外設 prefix，
以確保 path 與規格對齊（/api/v1/agents/{uid}/favorite）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.auth.schemas import TokenPayload
from app.schemas.response import ApiResponse
from app.schemas.social.schemas import (
    FavoriteToggleResponse,
    MyFavoritesResponse,
)
from app.services import favorite_service

router = APIRouter(tags=["social"])


@router.post(
    "/agents/{agent_uid}/favorite",
    response_model=ApiResponse[FavoriteToggleResponse],
    summary="收藏 Agent",
    description=(
        "將指定 Agent 加入目前使用者的收藏。idempotent：重複呼叫不會重複增加 "
        "`favorite_count`。若曾軟刪則復活。"
    ),
)
async def favorite_agent(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await favorite_service.add_favorite(
        current_user.user_uid, current_user.role, "agent", agent_uid, db
    )
    return success(data=result)


@router.delete(
    "/agents/{agent_uid}/favorite",
    response_model=ApiResponse[FavoriteToggleResponse],
    summary="取消收藏 Agent",
    description=(
        "取消收藏指定 Agent。idempotent：未收藏時不會讓 `favorite_count` 變負。"
    ),
)
async def unfavorite_agent(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await favorite_service.remove_favorite(
        current_user.user_uid, "agent", agent_uid, db
    )
    return success(data=result)


@router.post(
    "/skills/{skill_uid}/favorite",
    response_model=ApiResponse[FavoriteToggleResponse],
    summary="收藏 Skill",
    description=(
        "將指定 Skill 加入目前使用者的收藏。idempotent：重複呼叫不會重複增加 "
        "`favorite_count`。若曾軟刪則復活。"
    ),
)
async def favorite_skill(
    skill_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await favorite_service.add_favorite(
        current_user.user_uid, current_user.role, "skill", skill_uid, db
    )
    return success(data=result)


@router.delete(
    "/skills/{skill_uid}/favorite",
    response_model=ApiResponse[FavoriteToggleResponse],
    summary="取消收藏 Skill",
    description=(
        "取消收藏指定 Skill。idempotent：未收藏時不會讓 `favorite_count` 變負。"
    ),
)
async def unfavorite_skill(
    skill_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await favorite_service.remove_favorite(
        current_user.user_uid, "skill", skill_uid, db
    )
    return success(data=result)


@router.post(
    "/scripts/{script_uid}/favorite",
    response_model=ApiResponse[FavoriteToggleResponse],
    summary="收藏 Script",
    description=(
        "將指定 Script 加入目前使用者的收藏。idempotent：重複呼叫不會重複增加 "
        "`favorite_count`。若曾軟刪則復活。"
    ),
)
async def favorite_script(
    script_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await favorite_service.add_favorite(
        current_user.user_uid, current_user.role, "script", script_uid, db
    )
    return success(data=result)


@router.delete(
    "/scripts/{script_uid}/favorite",
    response_model=ApiResponse[FavoriteToggleResponse],
    summary="取消收藏 Script",
    description=(
        "取消收藏指定 Script。idempotent：未收藏時不會讓 `favorite_count` 變負。"
    ),
)
async def unfavorite_script(
    script_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await favorite_service.remove_favorite(
        current_user.user_uid, "script", script_uid, db
    )
    return success(data=result)


@router.get(
    "/users/me/favorites",
    response_model=ApiResponse[MyFavoritesResponse],
    summary="列出我的收藏",
    description=(
        "依收藏時間 desc 列出當前使用者的收藏。資源已被軟刪 / 遺失 → `resource=null` "
        "+ `tombstone_reason=\"resource_removed\"`，前端據此渲染 tombstone 卡片。"
    ),
)
async def list_my_favorites(
    type: str | None = Query(
        None,
        description="資源類型過濾：agent / skill / script；未帶則回全部",
        pattern="^(agent|skill|script)$",
    ),
    page: int = Query(1, ge=1, description="頁碼（從 1 開始）"),
    size: int = Query(20, ge=1, le=100, description="每頁筆數"),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await favorite_service.list_my_favorites(
        current_user.user_uid, type, page, size, db
    )
    return success(data=result)
