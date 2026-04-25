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
from app.schemas.chat.three_layer_memory_schemas import (
    AggregateTriggerResult,
    ProjectMemoryListData,
    ThreeLayerRagResult,
    UserMemoryListData,
)
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


class SkillFactoryStatsScopeSummary(BaseModel):
    approve_rate: float
    reject_rate: float


class SkillFactoryStatsData(BaseModel):
    """v1.3.6：依 scope / status 拆桶計數 + approve / reject 比率（給閾值調校監控用）。"""

    breakdown: dict[str, dict[str, int]]
    summary: dict[str, SkillFactoryStatsScopeSummary]


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
    scope: str | None = Query(
        None,
        description="v1.3.6：可篩選 scope=session|project|user",
        pattern="^(session|project|user)$",
    ),
) -> JSONResponse:
    """讀取 agentic:skill:log Redis stream 最近 N 筆事件（開發者觀察用）。

    v1.3.6：可指定 `scope` 篩選對應子分類。
    """
    result = await skill_factory_service.list_recent_logs(limit, scope=scope)
    return success(data=result)


@router.get(
    "/debug/skill-factory/stats",
    response_model=ApiResponse[SkillFactoryStatsData],
    summary="Skill 工廠 suggestion 拆桶計數（給閾值調校監控用）",
    description=(
        "v1.3.6：依 scope / status 拆桶計數，並回 approve / reject 比率。\n"
        "資料源為 agentic_skill_suggestion 表（30 天保留視窗）。"
    ),
)
async def get_skill_factory_stats(
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await skill_factory_service.get_skill_factory_stats(db)
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


# ============================================================
# v1.3.5 跨層記憶（admin only）：
# - 列三層記憶（admin 管理頁 / debug 用）
# - 手動觸發 project / user 聚合 worker
# - 檢索診斷：三層未融合 + 融合後完整結果
# ============================================================


@router.get(
    "/memory/projects/{chat_project_uid}",
    response_model=ApiResponse[ProjectMemoryListData],
    summary="列出指定 project 的 project_memory（不含 embedding）",
    description="v1.3.5：給 admin 管理頁 / 診斷頁觀察 project 層聚合結果。",
)
async def list_admin_project_memories(
    chat_project_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.list_project_memories(chat_project_uid, db)
    return success(data=result)


@router.get(
    "/memory/users/{user_uid}",
    response_model=ApiResponse[UserMemoryListData],
    summary="列出指定 user 的 user_memory",
    description="v1.3.5：給 admin 管理頁 / 診斷頁觀察 user 層長期偏好。",
)
async def list_admin_user_memories(
    user_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.list_user_memories(user_uid, db)
    return success(data=result)


@router.post(
    "/memory/aggregate/project/{chat_project_uid}",
    response_model=ApiResponse[AggregateTriggerResult],
    summary="手動觸發 project 二次聚合",
    description=(
        "v1.3.5：LPUSH 觸發訊號至 `project:memory:queue`，由 project_memory_worker 消費。\n"
        "可帶 `owner_user_uid` query 參數（給 metering 用，可省）。"
    ),
)
async def trigger_project_aggregate(
    chat_project_uid: str,
    _current_user: TokenPayload = require_role("admin"),
    owner_user_uid: str | None = Query(
        None, description="該 project 的 owner（給 metering 用，可省）"
    ),
) -> JSONResponse:
    result = await admin_service.queue_project_aggregate(
        chat_project_uid, owner_user_uid
    )
    return success(data=result)


@router.post(
    "/memory/aggregate/user/{user_uid}",
    response_model=ApiResponse[AggregateTriggerResult],
    summary="手動觸發 user 長期偏好聚合",
    description=(
        "v1.3.5：LPUSH 觸發訊號至 `user:memory:queue`，由 user_memory_worker 消費。\n"
        "聚合條件由 system_setting 的 N（min_session_count）/ M（topic_concentration_pct）決定。"
    ),
)
async def trigger_user_aggregate(
    user_uid: str,
    _current_user: TokenPayload = require_role("admin"),
) -> JSONResponse:
    result = await admin_service.queue_user_aggregate(user_uid)
    return success(data=result)


@router.get(
    "/debug/memory/retrieve",
    response_model=ApiResponse[ThreeLayerRagResult],
    summary="三層 RAG 檢索診斷（未融合 + RRF 融合）",
    description=(
        "v1.3.5：對指定 session 跑一次三層 RAG 完整流程，回傳每層 raw 結果與 RRF 融合結果。\n"
        "對齊 propose §3-4 層 3『檢索診斷』。"
    ),
)
async def debug_three_layer_retrieve(
    _current_user: TokenPayload = require_role("admin"),
    session_uid: str = Query(..., description="目標 session uid"),
    query: str = Query(..., description="檢索 query 文字"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await admin_service.debug_three_layer_retrieve(
        session_uid, query, db
    )
    return success(data=result)
