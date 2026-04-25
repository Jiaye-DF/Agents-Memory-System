from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.core.response import success
from app.schemas.admin.memory_debug import MemoryTraceData
from app.schemas.admin.metrics_schemas import (
    CostMetricsResponse,
    GroupByKey,
    RangeKey,
)
from app.schemas.admin.schemas import RoleResponse, UserResponse, UserUpdateRequest
from app.schemas.agent_languages.schemas import (
    AgentLanguageCreateRequest,
    AgentLanguageResponse,
    AgentLanguageUpdateRequest,
)
from app.schemas.agent_templates.schemas import (
    AgentTemplateCreateRequest,
    AgentTemplateResponse,
    AgentTemplateUpdateRequest,
)
from app.schemas.auth.schemas import TokenPayload
from app.schemas.models.schemas import (
    LlmModelAdminResponse,
    LlmModelCreateRequest,
    LlmModelUpdateRequest,
)
from app.schemas.response import (
    ApiResponse,
    MessageData,
    PaginatedData,
)
from app.schemas.settings.schemas import (
    SystemSettingResponse,
    SystemSettingUpdateRequest,
)
from app.services import (
    admin_metrics_service,
    admin_service,
    agent_language_service,
    agent_template_service,
    llm_model_service,
    skill_factory_service,
    system_setting_service,
)


class RolesListData(BaseModel):
    roles: list[RoleResponse]


class SystemSettingListData(BaseModel):
    items: list[SystemSettingResponse]


class SkillFactoryLogItem(BaseModel):
    id: str
    ts: str | None = None
    event: dict


class SkillFactoryLogListData(BaseModel):
    items: list[SkillFactoryLogItem]


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/users",
    response_model=ApiResponse[PaginatedData[UserResponse]],
)
async def list_users(
    _current_user: TokenPayload = require_role("admin"),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.list_users(cursor, limit, db)
    return success(data=result)


@router.get("/users/{user_uid}", response_model=ApiResponse[UserResponse])
async def get_user(
    user_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.get_user(user_uid, db)
    return success(data=result)


@router.put("/users/{user_uid}", response_model=ApiResponse[UserResponse])
async def update_user(
    user_uid: str,
    data: UserUpdateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.update_user(user_uid, data, db)
    return success(data=result)


@router.post(
    "/users/{user_uid}/disable",
    response_model=ApiResponse[UserResponse],
    summary="停用使用者並連動清除三層記憶",
    description=(
        "v1.3.5：停用 user 同 transaction 連動 hard delete：\n"
        "- 該 user 全部 chat_memory\n"
        "- 該 user 名下所有 project 的 project_memory\n"
        "- 該 user 的 user_memory\n"
        "對齊 propose §3-3 / Arch §5-2 表格『User 停用 / 刪除』。"
    ),
)
async def disable_user_endpoint(
    user_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.disable_user(user_uid, db)
    return success(data=result)


@router.get("/roles", response_model=ApiResponse[RolesListData])
async def list_roles(
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.list_roles(db)
    return success(data=result)


@router.get(
    "/llm-models",
    response_model=ApiResponse[PaginatedData[LlmModelAdminResponse]],
)
async def list_llm_models(
    _current_user: TokenPayload = require_role("admin"),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await llm_model_service.list_models_admin(cursor, limit, db)
    return success(data=result)


@router.post(
    "/llm-models",
    response_model=ApiResponse[LlmModelAdminResponse],
)
async def create_llm_model(
    data: LlmModelCreateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await llm_model_service.create_model(data, db)
    return success(data=result, response_code=201)


@router.get(
    "/llm-models/{llm_model_uid}",
    response_model=ApiResponse[LlmModelAdminResponse],
)
async def get_llm_model(
    llm_model_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await llm_model_service.get_model(llm_model_uid, db)
    return success(data=result)


@router.put(
    "/llm-models/{llm_model_uid}",
    response_model=ApiResponse[LlmModelAdminResponse],
)
async def update_llm_model(
    llm_model_uid: str,
    data: LlmModelUpdateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await llm_model_service.update_model(llm_model_uid, data, db)
    return success(data=result)


@router.delete(
    "/llm-models/{llm_model_uid}",
    response_model=ApiResponse[MessageData],
)
async def delete_llm_model(
    llm_model_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await llm_model_service.delete_model(llm_model_uid, db)
    return success(data={"message": "模型已刪除"})


# ============================================================
# Agent 語言管理
# ============================================================


@router.get(
    "/agent-languages",
    response_model=ApiResponse[PaginatedData[AgentLanguageResponse]],
)
async def list_agent_languages_admin(
    _current_user: TokenPayload = require_role("admin"),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_language_service.list_languages_admin(
        cursor, limit, db
    )
    return success(data=result)


@router.post(
    "/agent-languages",
    response_model=ApiResponse[AgentLanguageResponse],
)
async def create_agent_language(
    data: AgentLanguageCreateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_language_service.create_language(data, db)
    return success(data=result, response_code=201)


@router.get(
    "/agent-languages/{agent_language_uid}",
    response_model=ApiResponse[AgentLanguageResponse],
)
async def get_agent_language(
    agent_language_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_language_service.get_language(agent_language_uid, db)
    return success(data=result)


@router.put(
    "/agent-languages/{agent_language_uid}",
    response_model=ApiResponse[AgentLanguageResponse],
)
async def update_agent_language(
    agent_language_uid: str,
    data: AgentLanguageUpdateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_language_service.update_language(
        agent_language_uid, data, db
    )
    return success(data=result)


@router.delete(
    "/agent-languages/{agent_language_uid}",
    response_model=ApiResponse[MessageData],
)
async def delete_agent_language(
    agent_language_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await agent_language_service.delete_language(agent_language_uid, db)
    return success(data={"message": "語言已刪除"})


# ============================================================
# 系統設定管理
# ============================================================


@router.get(
    "/settings",
    response_model=ApiResponse[SystemSettingListData],
)
async def list_settings_admin(
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await system_setting_service.list_admin(db)
    return success(data=result)


@router.get(
    "/settings/{key}",
    response_model=ApiResponse[SystemSettingResponse],
)
async def get_setting_admin(
    key: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await system_setting_service.get_setting(key, db)
    return success(data=result)


@router.put(
    "/settings/{key}",
    response_model=ApiResponse[SystemSettingResponse],
)
async def update_setting_admin(
    key: str,
    data: SystemSettingUpdateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await system_setting_service.update_setting(key, data, db)
    return success(data=result)


# ============================================================
# Agent 範本管理
# ============================================================


@router.get(
    "/agent-templates",
    response_model=ApiResponse[PaginatedData[AgentTemplateResponse]],
)
async def list_agent_templates_admin(
    _current_user: TokenPayload = require_role("admin"),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_template_service.list_templates_admin(
        cursor, limit, db
    )
    return success(data=result)


@router.post(
    "/agent-templates",
    response_model=ApiResponse[AgentTemplateResponse],
)
async def create_agent_template(
    data: AgentTemplateCreateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_template_service.create_template(data, db)
    return success(data=result, response_code=201)


@router.get(
    "/agent-templates/{agent_template_uid}",
    response_model=ApiResponse[AgentTemplateResponse],
)
async def get_agent_template(
    agent_template_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_template_service.get_template(agent_template_uid, db)
    return success(data=result)


@router.put(
    "/agent-templates/{agent_template_uid}",
    response_model=ApiResponse[AgentTemplateResponse],
)
async def update_agent_template(
    agent_template_uid: str,
    data: AgentTemplateUpdateRequest,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_template_service.update_template(
        agent_template_uid, data, db
    )
    return success(data=result)


@router.delete(
    "/agent-templates/{agent_template_uid}",
    response_model=ApiResponse[MessageData],
)
async def delete_agent_template(
    agent_template_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await agent_template_service.delete_template(agent_template_uid, db)
    return success(data={"message": "範本已刪除"})


# ============================================================
# v1.1.7 Skill 工廠觀察性：admin debug 端點
# ============================================================


@router.get(
    "/debug/skill-factory/recent",
    response_model=ApiResponse[SkillFactoryLogListData],
)
async def get_skill_factory_recent_logs(
    _current_user: TokenPayload = require_role("admin"),
    limit: int = Query(50, ge=1, le=200),
) -> JSONResponse:
    """讀取 agentic:skill:log Redis stream 最近 N 筆事件（開發者觀察用）。"""
    result = await skill_factory_service.list_recent_logs(limit)
    return success(data=result)


# ============================================================
# v1.3.0 LLM 呼叫成本 / 延遲 metrics（admin only）
# ============================================================


@router.get(
    "/metrics/cost",
    response_model=ApiResponse[CostMetricsResponse],
    summary="取得 LLM 呼叫成本 metrics（actual / counterfactual baseline / 省了多少）",
    description=(
        "依 range（today / 7d / 30d / month）+ group_by（route / model / user / "
        "session / purpose）切片回傳 actual / baseline 成本與省下的金額。\n"
        "資料來源為 llm_call_log 表（運營資料，30 天保留）。\n"
        "詳見 docs/Arch/01-observability-and-metrics.md §5-5。"
    ),
)
async def get_cost_metrics(
    _current_user: TokenPayload = require_role("admin"),
    range: RangeKey = Query("today", description="查詢區間"),
    group_by: GroupByKey = Query("route", description="切片維度"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """成本 metrics 查詢端點（admin 限定）。

    response shape 對齊 docs/Arch/01-observability-and-metrics.md §5-5；
    空資料時 `total_actual_usd` / `total_baseline_usd` / `saved_usd` 皆為 0、
    `breakdown` 為空陣列（不 raise）。
    """
    result = await admin_metrics_service.get_cost_metrics(range, group_by, db)
    return success(data=result)


# ============================================================
# v1.3.1 記憶 pipeline trace（admin only）
# ============================================================


@router.get(
    "/debug/memory/sessions/{session_uid}",
    response_model=ApiResponse[MemoryTraceData],
    summary="查詢 session 的記憶 pipeline trace",
    description=(
        "讀取 Redis stream `memory:trace:{session_uid}` 的全程 trace，"
        "依時間升序回傳；找不到時回 200 + items=[]。\n"
        "stream 由 memory_worker 各階段 XADD（MAXLEN ~ 200, TTL 7 天）。\n"
        "詳見 docs/Tasks/v1.3/tasks-v1.3.1.md §Phase 2。"
    ),
)
async def get_memory_session_trace(
    session_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    limit: int = Query(200, ge=1, le=500, description="最多回傳筆數"),
) -> JSONResponse:
    """取單一 session 的記憶 pipeline trace（admin 限定）。"""
    result = await admin_service.get_memory_trace(session_uid, limit)
    return success(data=result)
