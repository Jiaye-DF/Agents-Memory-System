from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.auth.schemas import TokenPayload
from app.schemas.response import ApiResponse, MessageData, PaginatedData
from app.schemas.common import VisibilityRequest
from app.schemas.skills.schemas import (
    FileContentResponse,
    FileTreeNode,
    SkillFileUpdateRequest,
    SkillResponse,
    SkillUpdateRequest,
    SkillUsageResponse,
)
from app.services import skill_service


class FileTreeData(BaseModel):
    tree: list[FileTreeNode]


class SkillFileUpdateData(BaseModel):
    file_path: str
    size: int
    updated_at: str | None
    new_content_preview: str


router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=ApiResponse[PaginatedData[SkillResponse]])
async def list_skills(
    current_user: TokenPayload = Depends(get_current_user),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await skill_service.list_skills(
        current_user.user_uid, cursor, limit, db
    )
    return success(data=result)


@router.post("", response_model=ApiResponse[SkillResponse])
async def upload_skill(
    files: list[UploadFile] = File(...),
    name: str = Form(...),
    description: str = Form(...),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await skill_service.upload_skill(
        current_user.user_uid, name, description, files, db
    )
    return success(data=result, response_code=201)


@router.get("/{skill_uid}", response_model=ApiResponse[SkillResponse])
async def get_skill(
    skill_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await skill_service.get_skill(
        skill_uid, current_user.user_uid, current_user.role, db
    )
    return success(data=result)


@router.put("/{skill_uid}", response_model=ApiResponse[SkillResponse])
async def update_skill(
    skill_uid: str,
    data: SkillUpdateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await skill_service.update_skill(
        skill_uid, current_user.user_uid, current_user.role, data, db
    )
    return success(data=result)


@router.delete("/{skill_uid}", response_model=ApiResponse[MessageData])
async def delete_skill(
    skill_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await skill_service.delete_skill(
        skill_uid, current_user.user_uid, current_user.role, db
    )
    return success(data={"message": "Skill 已刪除"})


@router.patch(
    "/{skill_uid}/visibility",
    response_model=ApiResponse[SkillResponse],
)
async def toggle_visibility(
    skill_uid: str,
    data: VisibilityRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await skill_service.toggle_visibility(
        skill_uid, current_user.user_uid, data, db
    )
    return success(data=result)


@router.get("/{skill_uid}/download")
async def download_skill(
    skill_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    file_path, filename = await skill_service.download_skill(
        skill_uid, current_user.user_uid, current_user.role, db
    )
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip",
    )


@router.get(
    "/{skill_uid}/tree",
    response_model=ApiResponse[FileTreeData],
)
async def get_file_tree(
    skill_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    tree = await skill_service.get_file_tree(
        skill_uid, current_user.user_uid, current_user.role, db
    )
    return success(data={"tree": [node.model_dump() for node in tree]})


@router.get(
    "/{skill_uid}/file",
    response_model=ApiResponse[FileContentResponse],
)
async def get_file_content(
    skill_uid: str,
    path: str = Query(..., min_length=1),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await skill_service.get_file_content(
        skill_uid, current_user.user_uid, current_user.role, path, db
    )
    return success(data=result)


@router.get(
    "/{skill_uid}/usage",
    response_model=ApiResponse[SkillUsageResponse],
)
async def get_skill_usage(
    skill_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await skill_service.get_usage(
        skill_uid, current_user.user_uid, current_user.role, db
    )
    return success(data=result)


@router.post(
    "/{skill_uid}/reupload",
    response_model=ApiResponse[SkillResponse],
)
async def reupload_skill(
    skill_uid: str,
    files: list[UploadFile] = File(...),
    expected_updated_at: str = Form(...),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await skill_service.reupload_skill(
        skill_uid,
        current_user.user_uid,
        current_user.role,
        files,
        expected_updated_at,
        db,
    )
    return success(data=result)


@router.put(
    "/{skill_uid}/file",
    response_model=ApiResponse[SkillFileUpdateData],
)
async def update_skill_file(
    skill_uid: str,
    data: SkillFileUpdateRequest,
    path: str = Query(..., min_length=1),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await skill_service.update_file_content(
        skill_uid,
        current_user.user_uid,
        path,
        data.content,
        data.expected_updated_at,
        db,
    )
    return success(data=result)
