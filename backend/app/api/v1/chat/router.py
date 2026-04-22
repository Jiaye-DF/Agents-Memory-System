import io
import urllib.parse

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
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
)
from app.schemas.response import ApiResponse, MessageData, PaginatedData
from app.services import chat_attachment_service, chat_service

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
