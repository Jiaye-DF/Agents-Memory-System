"""Script（腳本資源）相關路由。

規格：docs/Tasks/v1.2/tasks-v1.2.3.md §A-6 / v1.2.5 §1-3 / propose-v1.2.0.md §2-3

端點：
- GET    /api/v1/scripts?cursor=&limit=&order_by=&order=
- GET    /api/v1/scripts/public?cursor=&limit=&order_by=&order=  （v1.2.5 新增，回所有公開）
- POST   /api/v1/scripts                 （multipart：files[], relative_paths[], name, description?, visibility?）
- GET    /api/v1/scripts/{uid}
- PATCH  /api/v1/scripts/{uid}           （可切換 name / description / visibility）
- DELETE /api/v1/scripts/{uid}           （soft delete）
- GET    /api/v1/scripts/{uid}/download  （StreamingResponse 豁免統一回應格式）

注意：收藏 API（`POST/DELETE /api/v1/scripts/{uid}/favorite`）在 `social/router.py` 補。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.auth.schemas import TokenPayload
from app.schemas.response import ApiResponse, MessageData, PaginatedData
from app.schemas.scripts.schemas import (
    ScriptResponse,
    ScriptUpdateRequest,
)
from app.services import script_service

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("", response_model=ApiResponse[PaginatedData[ScriptResponse]])
async def list_scripts(
    current_user: TokenPayload = Depends(get_current_user),
    cursor: str | None = Query(None, description="分頁游標（由上一頁回傳）"),
    limit: int = Query(20, ge=1, le=50, description="每頁筆數"),
    order_by: Literal[
        "favorite_count", "download_count", "created_at", "updated_at"
    ]
    | None = Query(
        None,
        description=(
            "排序欄位（白名單）：favorite_count / download_count / created_at / "
            "updated_at；未指定時維持 pid 升序（向下相容）"
        ),
    ),
    order: Literal["asc", "desc"] = Query(
        "desc",
        description="排序方向：desc（預設）/ asc；僅在有指定 order_by 時生效",
    ),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await script_service.list_scripts(
        current_user.user_uid, cursor, limit, db, order_by=order_by, order=order
    )
    return success(data=result)


@router.get(
    "/public",
    response_model=ApiResponse[PaginatedData[ScriptResponse]],
    summary="取得所有公開 Script（visibility='public'）",
    description=(
        "回傳所有 `visibility='public'` 的 Script。搭配 Dashboard 公開 Scripts 頁籤使用。"
        "排序白名單與 `GET /scripts` 相同。"
    ),
)
async def list_public_scripts(
    current_user: TokenPayload = Depends(get_current_user),
    cursor: str | None = Query(None, description="分頁游標（由上一頁回傳）"),
    limit: int = Query(20, ge=1, le=50, description="每頁筆數"),
    order_by: Literal[
        "favorite_count", "download_count", "created_at", "updated_at"
    ]
    | None = Query(
        None,
        description=(
            "排序欄位（白名單）：favorite_count / download_count / "
            "created_at / updated_at"
        ),
    ),
    order: Literal["asc", "desc"] = Query(
        "desc",
        description="排序方向：desc（預設）/ asc；僅在有指定 order_by 時生效",
    ),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await script_service.list_public_scripts(
        current_user.user_uid, cursor, limit, db, order_by=order_by, order=order
    )
    return success(data=result)


@router.post("", response_model=ApiResponse[ScriptResponse])
async def create_script(
    files: list[UploadFile] = File(
        ..., description="上傳的檔案集合；使用 `webkitdirectory` 時為整個資料夾"
    ),
    relative_paths: list[str] = Form(
        ..., description="對應每個檔案的相對路徑（與 files 數量一致）"
    ),
    name: str = Form(..., description="Script 名稱"),
    description: str = Form(..., description="Script 描述"),
    visibility: Literal["public", "private"] | None = Form(
        None,
        description="可見性：public / private；未指定時 DB DEFAULT 'private'",
    ),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await script_service.create_script(
        current_user.user_uid,
        name,
        description,
        files,
        relative_paths,
        db,
        visibility=visibility,
    )
    return success(data=result, response_code=201)


@router.get("/{script_uid}", response_model=ApiResponse[ScriptResponse])
async def get_script(
    script_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await script_service.get_script(
        script_uid, current_user.user_uid, current_user.role, db
    )
    return success(data=result)


@router.patch("/{script_uid}", response_model=ApiResponse[ScriptResponse])
async def update_script(
    script_uid: str,
    data: ScriptUpdateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await script_service.update_script(
        script_uid, current_user.user_uid, current_user.role, data, db
    )
    return success(data=result)


@router.delete("/{script_uid}", response_model=ApiResponse[MessageData])
async def delete_script(
    script_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await script_service.soft_delete_script(
        script_uid, current_user.user_uid, current_user.role, db
    )
    return success(data={"message": "Script 已刪除"})


@router.get("/{script_uid}/download")
async def download_script(
    script_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """下載 Script zip；**豁免**統一回應格式（與 Skill download 一致）。"""
    file_path, filename = await script_service.download_script(
        script_uid, current_user.user_uid, current_user.role, db
    )
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip",
    )
