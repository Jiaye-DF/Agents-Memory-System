"""儀錶板（Dashboard）相關路由。

規格：docs/Tasks/v1.2/tasks-v1.2.4.md §1-4 / propose-v1.2.0.md §2-4

端點：
- `GET /api/v1/dashboard/rankings?type=&order_by=&limit=`
  - 跨 Agent / Skill / Script 三類資源的排行榜
  - `type` / `order_by` 嚴格白名單（FastAPI `Literal`），不在白名單的值回 422
  - `limit` 未傳時由 service 依 `dashboard.ranking_size` 解析（預設 10）
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.auth.schemas import TokenPayload
from app.schemas.dashboard.schemas import RankingResponse
from app.schemas.response import ApiResponse
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/rankings",
    response_model=ApiResponse[RankingResponse],
    summary="取得儀錶板排行榜",
    description=(
        "跨 Agent / Skill / Script 三類資源的 top-N 排行榜。"
        "`type=all` 時三類混排；指定單類時僅回該類。"
        "排序欄位 `order_by`：`download_count` / `favorite_count` / `created_at`；"
        "排序方向 `order`：`desc`（預設）/ `asc`（v1.2.5 新增）。"
        "`limit` 未傳時以 `dashboard.ranking_size` 為準（預設 10）。"
        "本版僅顯示當前使用者擁有的資源，跨使用者公開排行留 v1.4。"
    ),
)
async def get_rankings(
    type: Literal["all", "agent", "skill", "script"] = Query(
        "all",
        description="資源類型過濾：all / agent / skill / script",
    ),
    order_by: Literal["download_count", "favorite_count", "created_at"] = Query(
        "download_count",
        description="排序欄位",
    ),
    order: Literal["asc", "desc"] = Query(
        "desc",
        description="排序方向：desc（預設）/ asc；v1.2.5 新增",
    ),
    limit: int | None = Query(
        None,
        ge=1,
        le=100,
        description="top N 數量；未帶則以系統設定 `dashboard.ranking_size` 為準（預設 10）",
    ),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await dashboard_service.list_rankings(
        current_user.user_uid, type, order_by, db, limit=limit, order=order
    )
    return success(data=result)
