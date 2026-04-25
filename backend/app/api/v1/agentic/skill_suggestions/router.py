"""個人視角 Skill Suggestion API（v1.3.6 Phase 4-1）。

router prefix `/api/v1/skill-suggestions`，全部端點需登入；ownership 由
service 層 `get_by_uid(uid, owner_user_uid)` 自動驗證（非擁有者視同 404，
不洩漏存在性差異）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.agentic.skill_suggestion_schemas import (
    AgenticSkillSuggestionAcceptRequest,
    AgenticSkillSuggestionAcceptResponse,
    AgenticSkillSuggestionDetailResponse,
    AgenticSkillSuggestionListResponse,
    AgenticSkillSuggestionRejectResponse,
    SuggestionScope,
    SuggestionStatus,
)
from app.schemas.auth.schemas import TokenPayload
from app.schemas.response import ApiResponse
from app.services import agentic_skill_suggestion_service

router = APIRouter(prefix="/skill-suggestions", tags=["skill-suggestions"])


@router.get(
    "",
    response_model=ApiResponse[AgenticSkillSuggestionListResponse],
    summary="列出當前使用者的 Skill 候選",
    description=(
        "v1.3.6：列出三 scope（session / project / user）的 Skill 候選。\n\n"
        "- 預設 status=pending；不指定則回所有狀態（含 expired / approved / rejected）\n"
        "- scope 不指定則回三 scope 全部\n"
        "- 進入時 lazy 標記過期（>30 天 pending → expired）"
    ),
)
async def list_skill_suggestions(
    current_user: TokenPayload = Depends(get_current_user),
    scope: SuggestionScope | None = Query(
        None, description="範圍篩選：session / project / user"
    ),
    status: SuggestionStatus | None = Query(
        "pending",
        description="狀態篩選；傳空字串或 status=all 視同不限狀態",
    ),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    # 允許前端用 status=all 取消篩選
    effective_status: str | None
    if status in (None, "all", ""):
        effective_status = None
    else:
        effective_status = status

    result = await agentic_skill_suggestion_service.list_suggestions(
        user_uid=current_user.user_uid,
        scope=scope,
        status=effective_status,
        page=page,
        size=size,
        db=db,
    )
    await db.commit()
    return success(data=result)


@router.get(
    "/{uid}",
    response_model=ApiResponse[AgenticSkillSuggestionDetailResponse],
    summary="取得單筆 Skill 候選詳情（含來源記憶 inline 摘要）",
)
async def get_skill_suggestion_detail(
    uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agentic_skill_suggestion_service.get_suggestion_detail(
        user_uid=current_user.user_uid,
        suggestion_uid=uid,
        db=db,
    )
    return success(data=result)


@router.post(
    "/{uid}/accept",
    response_model=ApiResponse[AgenticSkillSuggestionAcceptResponse],
    summary="接受 Skill 候選並建立 skill（可選掛載到指定 Agent）",
    description=(
        "打包 system_prompt 為 prompt.md 進單檔 zip → 沿用 POST /skills 流程建立 Skill。\n\n"
        "若帶入 `agent_uid` 則同步將新 skill_uid 加入該 Agent 的 skill_uids "
        "（驗證 Agent 屬於 current user，否則 404）。"
    ),
)
async def accept_skill_suggestion(
    uid: str,
    body: AgenticSkillSuggestionAcceptRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agentic_skill_suggestion_service.accept_suggestion(
        user_uid=current_user.user_uid,
        suggestion_uid=uid,
        agent_uid=body.agent_uid,
        db=db,
    )
    await db.commit()
    return success(data=result, response_code=201)


@router.post(
    "/{uid}/reject",
    response_model=ApiResponse[AgenticSkillSuggestionRejectResponse],
    summary="拒絕 Skill 候選",
)
async def reject_skill_suggestion(
    uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agentic_skill_suggestion_service.reject_suggestion(
        user_uid=current_user.user_uid,
        suggestion_uid=uid,
        db=db,
    )
    await db.commit()
    return success(data=result)
