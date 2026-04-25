from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import AppError
from app.core.response import success
from app.schemas.agents.schemas import (
    AgentCreateRequest,
    AgentResponse,
    AgentUpdateRequest,
)
from app.schemas.agentic.skill_suggestion_schemas import (
    AgenticSkillSuggestionAcceptResponse,
    AgenticSkillSuggestionRejectResponse,
    RecommendSuggestionListResponse,
)
from app.schemas.common import VisibilityRequest
from app.schemas.auth.schemas import TokenPayload
from app.schemas.response import ApiResponse, MessageData, PaginatedData
from app.services import (
    agent_service,
    agentic_skill_suggestion_service,
    skill_recommender_service,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=ApiResponse[PaginatedData[AgentResponse]])
async def list_agents(
    current_user: TokenPayload = Depends(get_current_user),
    cursor: str | None = Query(None, description="分頁游標（由上一頁回傳）"),
    limit: int = Query(20, ge=1, le=50, description="每頁筆數"),
    order_by: str | None = Query(
        None,
        description=(
            "排序欄位（白名單）：favorite_count / download_count / created_at / "
            "updated_at；未指定時維持 pid 升序（向下相容）"
        ),
        pattern="^(favorite_count|download_count|created_at|updated_at)$",
    ),
    order: str = Query(
        "desc",
        description="排序方向：desc（預設）/ asc；僅在有指定 order_by 時生效",
        pattern="^(asc|desc)$",
    ),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.list_agents(
        current_user.user_uid, cursor, limit, db, order_by=order_by, order=order
    )
    return success(data=result)


@router.post("", response_model=ApiResponse[AgentResponse])
async def create_agent(
    data: AgentCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.create_agent(
        current_user.user_uid, data, db
    )
    return success(data=result, response_code=201)


@router.get("/{agent_uid}", response_model=ApiResponse[AgentResponse])
async def get_agent(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.get_agent(
        agent_uid, current_user.user_uid, current_user.role, db
    )
    return success(data=result)


@router.put("/{agent_uid}", response_model=ApiResponse[AgentResponse])
async def update_agent(
    agent_uid: str,
    data: AgentUpdateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.update_agent(
        agent_uid, current_user.user_uid, current_user.role, data, db
    )
    return success(data=result)


@router.delete("/{agent_uid}", response_model=ApiResponse[MessageData])
async def delete_agent(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await agent_service.delete_agent(
        agent_uid, current_user.user_uid, current_user.role, db
    )
    return success(data={"message": "Agent 已刪除"})


@router.patch(
    "/{agent_uid}/visibility",
    response_model=ApiResponse[AgentResponse],
)
async def toggle_visibility(
    agent_uid: str,
    data: VisibilityRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.toggle_visibility(
        agent_uid, current_user.user_uid, data, db
    )
    return success(data=result)


@router.get("/{agent_uid}/download")
async def download_agent(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    content = await agent_service.download_agent(
        agent_uid, current_user.user_uid, current_user.role, db
    )
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=AGENTS.md"},
    )


# ---------- Skill 推薦（v1.3.6 取代 v1.3.3 stub） ----------


@router.get(
    "/{agent_uid}/skill-suggestions",
    response_model=ApiResponse[RecommendSuggestionListResponse],
    tags=["skills"],
    summary="列出該使用者對指定 Agent 的 Skill 推薦",
    description=(
        "v1.3.6：列出當前使用者 pending 中、confidence >= 推薦門檻、"
        "且尚未掛載到此 Agent 的 Skill 候選；不依賴訊息向量比對，"
        "適合 Agent 詳情頁 / 對話入口顯示「建議 N」徽章。"
    ),
)
async def list_agent_skill_suggestions(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    # 驗證 agent 存在 + 擁有權
    target_agent = await skill_recommender_service.ensure_agent_owned_by_user(
        agent_uid, current_user.user_uid, db
    )
    if target_agent is None:
        raise AppError(
            detail="找不到指定的 Agent 或無權限",
            response_code=404,
            status_code=404,
        )
    items = await skill_recommender_service.list_recommendations_for_agent(
        user_uid=current_user.user_uid,
        agent_uid=agent_uid,
        db=db,
    )
    return success(data={"items": items})


@router.post(
    "/{agent_uid}/skill-suggestions/{suggestion_uid}/accept",
    response_model=ApiResponse[AgenticSkillSuggestionAcceptResponse],
    tags=["skills"],
    summary="接受 Skill 候選並掛載到此 Agent",
    description=(
        "建立 Skill（沿用 POST /skills 流程）並強制掛載到 path 中的 Agent；"
        "等價於 `/api/v1/skill-suggestions/{uid}/accept` body 帶 agent_uid=path。"
    ),
)
async def accept_agent_skill_suggestion(
    agent_uid: str,
    suggestion_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    target_agent = await skill_recommender_service.ensure_agent_owned_by_user(
        agent_uid, current_user.user_uid, db
    )
    if target_agent is None:
        raise AppError(
            detail="找不到指定的 Agent 或無權限",
            response_code=404,
            status_code=404,
        )
    result = await agentic_skill_suggestion_service.accept_suggestion(
        user_uid=current_user.user_uid,
        suggestion_uid=suggestion_uid,
        agent_uid=agent_uid,
        db=db,
    )
    await db.commit()
    return success(data=result, response_code=201)


@router.post(
    "/{agent_uid}/skill-suggestions/{suggestion_uid}/reject",
    response_model=ApiResponse[AgenticSkillSuggestionRejectResponse],
    tags=["skills"],
    summary="拒絕 Skill 候選",
)
async def reject_agent_skill_suggestion(
    agent_uid: str,
    suggestion_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    target_agent = await skill_recommender_service.ensure_agent_owned_by_user(
        agent_uid, current_user.user_uid, db
    )
    if target_agent is None:
        raise AppError(
            detail="找不到指定的 Agent 或無權限",
            response_code=404,
            status_code=404,
        )
    result = await agentic_skill_suggestion_service.reject_suggestion(
        user_uid=current_user.user_uid,
        suggestion_uid=suggestion_uid,
        db=db,
    )
    await db.commit()
    return success(data=result)
