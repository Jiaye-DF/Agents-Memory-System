import io
import urllib.parse

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_from_query, get_db
from app.core.response import success
from app.schemas.auth.schemas import TokenPayload
from app.schemas.chat.attachment_schemas import ChatAttachmentListData
from app.schemas.chat.memory_schemas import ChatMemoryListData
from app.schemas.chat.schemas import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatProjectCreateRequest,
    ChatProjectResponse,
    ChatProjectUpdateRequest,
    ChatSessionCreateRequest,
    ChatSessionMoveRequest,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
    SessionAgentAddRequest,
    SessionAgentsListData,
)
from app.schemas.chat.skill_suggestion_schemas import (
    SkillSuggestionApproveData,
    SkillSuggestionListData,
)
from app.schemas.response import ApiResponse, MessageData, PaginatedData
from app.services import chat_attachment_service, chat_service
from app.services import chat_service, skill_factory_service

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------- Projects ----------

@router.get(
    "/projects",
    response_model=ApiResponse[PaginatedData[ChatProjectResponse]],
)
async def list_projects(
    current_user: TokenPayload = Depends(get_current_user),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.list_projects(
        current_user.user_uid, cursor, limit, db
    )
    return success(data=result)


@router.post("/projects", response_model=ApiResponse[ChatProjectResponse])
async def create_project(
    data: ChatProjectCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.create_project(current_user.user_uid, data, db)
    return success(data=result, response_code=201)


@router.get(
    "/projects/{chat_project_uid}",
    response_model=ApiResponse[ChatProjectResponse],
)
async def get_project(
    chat_project_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.get_project(
        chat_project_uid, current_user.user_uid, db
    )
    return success(data=result)


@router.put(
    "/projects/{chat_project_uid}",
    response_model=ApiResponse[ChatProjectResponse],
)
async def update_project(
    chat_project_uid: str,
    data: ChatProjectUpdateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.update_project(
        chat_project_uid, current_user.user_uid, data, db
    )
    return success(data=result)


@router.delete(
    "/projects/{chat_project_uid}",
    response_model=ApiResponse[MessageData],
)
async def delete_project(
    chat_project_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await chat_service.delete_project(
        chat_project_uid, current_user.user_uid, db
    )
    return success(data={"message": "Project 已刪除"})


@router.get(
    "/projects/{chat_project_uid}/sessions",
    response_model=ApiResponse[PaginatedData[ChatSessionResponse]],
)
async def list_sessions_by_project(
    chat_project_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.list_sessions(
        chat_project_uid, current_user.user_uid, cursor, limit, db
    )
    return success(data=result)


# ---------- Sessions ----------

@router.get(
    "/sessions",
    response_model=ApiResponse[PaginatedData[ChatSessionResponse]],
)
async def list_orphan_sessions(
    current_user: TokenPayload = Depends(get_current_user),
    orphan: bool = Query(
        True,
        description="v1.1.4 僅支援 orphan=true；傳其他值亦以游離 sessions 回傳",
    ),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """列出使用者自己的游離 sessions（不屬於任何 project）。"""
    del orphan  # 保留參數但 v1.1.4 僅支援 orphan list
    result = await chat_service.list_orphan_sessions(
        current_user.user_uid, cursor, limit, db
    )
    return success(data=result)


@router.post("/sessions", response_model=ApiResponse[ChatSessionResponse])
async def create_session(
    data: ChatSessionCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.create_session(current_user.user_uid, data, db)
    return success(data=result, response_code=201)


@router.post(
    "/sessions/{chat_session_uid}/move",
    response_model=ApiResponse[ChatSessionResponse],
)
async def move_session(
    chat_session_uid: str,
    data: ChatSessionMoveRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """把 session 移入 project 或移出為游離；target uid 為 None 代表游離。"""
    result = await chat_service.move_session(
        chat_session_uid, current_user.user_uid, data, db
    )
    return success(data=result)


@router.get(
    "/sessions/{chat_session_uid}",
    response_model=ApiResponse[ChatSessionResponse],
)
async def get_session(
    chat_session_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.get_session(
        chat_session_uid, current_user.user_uid, db
    )
    return success(data=result)


@router.put(
    "/sessions/{chat_session_uid}",
    response_model=ApiResponse[ChatSessionResponse],
)
async def update_session(
    chat_session_uid: str,
    data: ChatSessionUpdateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.update_session(
        chat_session_uid, current_user.user_uid, data, db
    )
    return success(data=result)


@router.delete(
    "/sessions/{chat_session_uid}",
    response_model=ApiResponse[MessageData],
)
async def delete_session(
    chat_session_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await chat_service.delete_session(
        chat_session_uid, current_user.user_uid, db
    )
    return success(data={"message": "Session 已刪除"})


# ---------- Session Agents (v1.3.3 多 Agent 對話) ----------

@router.get(
    "/sessions/{chat_session_uid}/agents",
    response_model=ApiResponse[SessionAgentsListData],
    summary="列出 session 已掛 Agent",
    description="回傳該 session 下所有有效掛載的 Agent（含 primary / member 角色）。",
)
async def list_session_agents(
    chat_session_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.list_session_agents(
        chat_session_uid, current_user.user_uid, db
    )
    return success(data=result)


@router.post(
    "/sessions/{chat_session_uid}/agents",
    response_model=ApiResponse[SessionAgentsListData],
    summary="加掛 Agent 至 session",
    description="加掛 Agent 至 session；超過 multi_agent.max_per_session 上限回 422。",
)
async def add_session_agent(
    chat_session_uid: str,
    data: SessionAgentAddRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.add_agent_to_session(
        chat_session_uid, data.agent_uid, current_user.user_uid, db
    )
    return success(data=result, response_code=201)


@router.delete(
    "/sessions/{chat_session_uid}/agents/{agent_uid}",
    response_model=ApiResponse[SessionAgentsListData],
    summary="移除 session 上的 Agent",
    description=(
        "從 session 移除指定 Agent。"
        "最後一個 Agent 不可移除（回 422 cannot_remove_last_agent）；"
        "移除 primary 時會自動將加入時間最早的 member 提升為 primary。"
    ),
)
async def remove_session_agent(
    chat_session_uid: str,
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.remove_agent_from_session(
        chat_session_uid, agent_uid, current_user.user_uid, db
    )
    return success(data=result)


@router.patch(
    "/sessions/{chat_session_uid}/agents/{agent_uid}/promote",
    response_model=ApiResponse[SessionAgentsListData],
    summary="把 Agent 設為 session 的 primary",
    description="將指定 Agent 設為 primary，原 primary 改為 member。Agent 必須是 session 成員。",
)
async def promote_session_agent(
    chat_session_uid: str,
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.promote_primary(
        chat_session_uid, agent_uid, current_user.user_uid, db
    )
    return success(data=result)


# ---------- Messages ----------

@router.get(
    "/sessions/{chat_session_uid}/messages",
    response_model=ApiResponse[PaginatedData[ChatMessageResponse]],
)
async def list_messages(
    chat_session_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await chat_service.list_messages(
        chat_session_uid, current_user.user_uid, cursor, limit, db
    )
    return success(data=result)


@router.get(
    "/sessions/{chat_session_uid}/memories",
    response_model=ApiResponse[ChatMemoryListData],
)
async def list_session_memories(
    chat_session_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """列出 session 下所有記憶（僅擁有者；不含 embedding）。"""
    result = await chat_service.list_memories(
        chat_session_uid, current_user.user_uid, db
    )
    return success(data=result)


# ---------- Skill Suggestions (v1.1.7 Agentic PoC) ----------


@router.get(
    "/sessions/{chat_session_uid}/skill-suggestions",
    response_model=ApiResponse[SkillSuggestionListData],
)
async def list_skill_suggestions(
    chat_session_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """列出該 session 目前的 Skill 候選（僅 session 擁有者可見）。"""
    result = await skill_factory_service.list_suggestions(
        current_user.user_uid, chat_session_uid, db
    )
    return success(data=result)


@router.post(
    "/sessions/{chat_session_uid}/skill-suggestions/{idx}/approve",
    response_model=ApiResponse[SkillSuggestionApproveData],
)
async def approve_skill_suggestion(
    chat_session_uid: str,
    idx: int,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """核准 Skill 候選並沿用 POST /skills 流程建立私人 skill。"""
    result = await skill_factory_service.approve_suggestion(
        current_user.user_uid, chat_session_uid, idx, db
    )
    return success(data=result, response_code=201)


@router.post(
    "/sessions/{chat_session_uid}/skill-suggestions/{idx}/reject",
    response_model=ApiResponse[MessageData],
)
async def reject_skill_suggestion(
    chat_session_uid: str,
    idx: int,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """拒絕 Skill 候選（標記為 rejected，保留在 Redis 供事後分析）。"""
    await skill_factory_service.reject_suggestion(
        current_user.user_uid, chat_session_uid, idx, db
    )
    return success(data={"message": "已拒絕該 Skill 候選"})


@router.get(
    "/sessions/{chat_session_uid}/events",
    summary="訂閱 Session 級別非同步事件（SSE）",
    description=(
        "v1.3.2：以 SSE 推送 memory_worker 寫入結果，前端收到後 invalidate 記憶 RTK Query tag。\n\n"
        "因 EventSource 不支援自訂 header，token 走 query string 驗證；非擁有者 / 不存在 session 一律 404。\n\n"
        "可能的事件：\n"
        "- `ready`：連線握手成功（payload `{session_uid}`），前端據此停掉 polling fallback。\n"
        "- `memory_updated`：memory_worker 寫入新 chat_memory（payload `{event, memory_uid, ts}`）。\n"
        "- `memory_failed`：DLQ 進入時觸發（payload `{event, message_uids, error, ts}`）；本版前端僅 log。\n"
        "- `session_archived`：保留型別，本版不觸發。\n\n"
        "另每 15 秒會送 SSE comment `: ping\\n\\n` 作 keep-alive。"
    ),
    responses={
        200: {
            "description": "SSE 事件流（text/event-stream）",
            "content": {"text/event-stream": {}},
        },
        401: {"description": "token 失效或缺漏"},
        404: {"description": "session 不存在或非擁有者"},
    },
)
async def subscribe_session_events_sse(
    chat_session_uid: str,
    token: str = Query(..., description="access token（EventSource 不支援自訂 header）"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # query string 驗證 access token；失敗回 401
    current_user = get_current_user_from_query(token)
    # 連線建立前先驗證 session 擁有者；非擁有者 / 不存在皆 404
    await chat_service.ensure_session_owner_for_events(
        chat_session_uid, current_user.user_uid, db
    )
    return StreamingResponse(
        chat_service.subscribe_session_events(chat_session_uid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{chat_session_uid}/messages")
async def send_message(
    chat_session_uid: str,
    data: ChatMessageCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    generator = chat_service.send_message(
        chat_session_uid,
        current_user.user_uid,
        data.content,
        db,
        attachment_uids=data.attachment_uids,
        mentioned_agent_uid=data.mentioned_agent_uid,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- Attachments ----------

@router.post(
    "/sessions/{chat_session_uid}/attachments",
    response_model=ApiResponse[ChatAttachmentListData],
)
async def upload_session_attachments(
    chat_session_uid: str,
    files: list[UploadFile] = File(...),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    items = await chat_attachment_service.upload_attachments(
        current_user.user_uid, chat_session_uid, files, db
    )
    return success(data={"items": items}, response_code=201)


@router.get("/attachments/{chat_attachment_uid}")
async def download_attachment(
    chat_attachment_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    下載 / 預覽附件。屬於 20-backend.md § 豁免端點（檔案下載）— 回非 JSON body。
    錯誤走全域 AppError handler（仍回 ApiResponse JSON）。
    """
    data, mime, file_name = await chat_attachment_service.get_attachment_content(
        chat_attachment_uid, current_user.user_uid, db
    )
    # 使用 RFC 5987 的 filename* 以安全承載非 ASCII 檔名
    disposition_name = urllib.parse.quote(file_name)
    headers = {
        "Content-Disposition": (
            f"inline; filename=\"{chat_attachment_uid}\"; "
            f"filename*=UTF-8''{disposition_name}"
        ),
        "Cache-Control": "private, max-age=300",
    }
    return StreamingResponse(
        io.BytesIO(data),
        media_type=mime or "application/octet-stream",
        headers=headers,
    )
