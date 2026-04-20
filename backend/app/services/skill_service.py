import logging
import mimetypes
import os
import uuid
import zipfile
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.skill import Skill
from app.repositories import skill_repository
from app.schemas.skills.schemas import FileTreeNode, SkillUpdateRequest, VisibilityRequest

logger = logging.getLogger(__name__)

BLOCKED_EXTENSIONS = {".exe"}
BLOCKED_MIME_TYPES = {
    "application/x-msdownload",
    "application/x-dosexec",
    "application/x-executable",
}

FILE_PREVIEW_MAX_BYTES = 512 * 1024


def _skill_to_dict(skill: Skill) -> dict:
    return {
        "skill_uid": str(skill.skill_uid),
        "owner_uid": str(skill.owner_uid),
        "owner_username": skill.owner.username if skill.owner else None,
        "name": skill.name,
        "description": skill.description,
        "original_filename": skill.original_filename,
        "file_size": skill.file_size,
        "visibility": skill.visibility,
        "is_active": skill.is_active,
        "created_at": skill.created_at.isoformat(),
        "updated_at": skill.updated_at.isoformat(),
    }


def _validate_file(file: UploadFile) -> None:
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext in BLOCKED_EXTENSIONS:
        raise AppError(
            detail="不允許上傳 .exe 檔案",
            response_code=400,
            status_code=400,
        )

    content_type = file.content_type or ""
    guessed_type = mimetypes.guess_type(filename)[0] or ""

    if content_type in BLOCKED_MIME_TYPES or guessed_type in BLOCKED_MIME_TYPES:
        raise AppError(
            detail="不允許上傳可執行檔案",
            response_code=400,
            status_code=400,
        )


async def upload_skill(
    user_uid: str,
    name: str,
    description: str,
    file: UploadFile,
    db: AsyncSession,
) -> dict:
    _validate_file(file)

    file_content = await file.read()
    file_size = len(file_content)

    if file_size > settings.SKILLS_MAX_FILE_SIZE:
        raise AppError(
            detail=f"檔案大小超過上限（{settings.SKILLS_MAX_FILE_SIZE // (1024 * 1024)} MB）",
            response_code=400,
            status_code=400,
        )

    if file_size == 0:
        raise AppError(
            detail="檔案內容為空",
            response_code=400,
            status_code=400,
        )

    skill_uid = uuid.uuid4()
    original_filename = file.filename or "unknown"
    zip_filename = f"{os.path.splitext(original_filename)[0]}.zip"

    skill_dir = Path(settings.SKILLS_UPLOAD_DIR) / str(skill_uid)
    skill_dir.mkdir(parents=True, exist_ok=True)

    zip_path = skill_dir / zip_filename

    try:
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(original_filename, file_content)
    except Exception:
        logger.exception("建立 ZIP 檔案失敗")
        raise AppError(
            detail="檔案儲存失敗，請稍後再試",
            response_code=500,
            status_code=500,
        )

    skill = await skill_repository.create(
        {
            "skill_uid": skill_uid,
            "owner_uid": user_uid,
            "name": name,
            "description": description,
            "file_path": str(zip_path),
            "original_filename": original_filename,
            "file_size": file_size,
        },
        db,
    )

    return _skill_to_dict(skill)


async def get_skill(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    if skill is None:
        raise AppError(
            detail="找不到指定的 Skill",
            response_code=404,
            status_code=404,
        )

    if role != "admin":
        if str(skill.owner_uid) != user_uid and skill.visibility != "public":
            raise AppError(
                detail="找不到指定的 Skill",
                response_code=404,
                status_code=404,
            )

    return _skill_to_dict(skill)


async def list_skills(
    user_uid: str, cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    decoded_cursor: int | None = None
    if cursor is not None:
        decoded_cursor = decode_cursor(cursor)

    rows = await skill_repository.list_own_and_public(
        user_uid, decoded_cursor, limit, db
    )

    has_next = len(rows) > limit
    items = rows[:limit]

    next_cursor: str | None = None
    if has_next and items:
        next_cursor = encode_cursor(items[-1].pid)

    return {
        "items": [_skill_to_dict(s) for s in items],
        "next_cursor": next_cursor,
        "has_next": has_next,
    }


async def update_skill(
    skill_uid: str,
    user_uid: str,
    role: str,
    data: SkillUpdateRequest,
    db: AsyncSession,
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    if skill is None:
        raise AppError(
            detail="找不到指定的 Skill",
            response_code=404,
            status_code=404,
        )

    if role != "admin" and str(skill.owner_uid) != user_uid:
        raise AppError(
            detail="找不到指定的 Skill",
            response_code=404,
            status_code=404,
        )

    update_data: dict = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description

    if not update_data:
        raise AppError(
            detail="未提供任何更新欄位",
            response_code=400,
            status_code=400,
        )

    await skill_repository.update(skill, update_data, db)
    return _skill_to_dict(skill)


async def delete_skill(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> None:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    if skill is None:
        raise AppError(
            detail="找不到指定的 Skill",
            response_code=404,
            status_code=404,
        )

    if str(skill.owner_uid) != user_uid:
        raise AppError(
            detail="只有擁有者可以刪除 Skill",
            response_code=403,
            status_code=403,
        )

    await skill_repository.soft_delete(skill, db)


async def toggle_visibility(
    skill_uid: str,
    user_uid: str,
    data: VisibilityRequest,
    db: AsyncSession,
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    if skill is None:
        raise AppError(
            detail="找不到指定的 Skill",
            response_code=404,
            status_code=404,
        )

    if str(skill.owner_uid) != user_uid:
        raise AppError(
            detail="只有擁有者可以切換可見性",
            response_code=403,
            status_code=403,
        )

    await skill_repository.update(skill, {"visibility": data.visibility}, db)
    return _skill_to_dict(skill)


async def download_skill(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> tuple[str, str]:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    if skill is None:
        raise AppError(
            detail="找不到指定的 Skill",
            response_code=404,
            status_code=404,
        )

    if role != "admin":
        if str(skill.owner_uid) != user_uid and skill.visibility != "public":
            raise AppError(
                detail="找不到指定的 Skill",
                response_code=404,
                status_code=404,
            )

    file_path = skill.file_path
    if not Path(file_path).exists():
        raise AppError(
            detail="檔案不存在，請聯繫管理員",
            response_code=404,
            status_code=404,
        )

    download_name = f"{os.path.splitext(skill.original_filename)[0]}.zip"
    return file_path, download_name


async def get_file_tree(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> list[FileTreeNode]:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    if skill is None:
        raise AppError(
            detail="找不到指定的 Skill",
            response_code=404,
            status_code=404,
        )

    if role != "admin":
        if str(skill.owner_uid) != user_uid and skill.visibility != "public":
            raise AppError(
                detail="找不到指定的 Skill",
                response_code=404,
                status_code=404,
            )

    file_path = skill.file_path
    if not Path(file_path).exists():
        raise AppError(
            detail="檔案不存在，請聯繫管理員",
            response_code=404,
            status_code=404,
        )

    tree: dict[str, FileTreeNode] = {}

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            for info in zf.infolist():
                parts = info.filename.rstrip("/").split("/")
                _build_tree(tree, parts, info.is_dir())
    except zipfile.BadZipFile:
        raise AppError(
            detail="檔案格式損毀，無法讀取",
            response_code=500,
            status_code=500,
        )

    return _tree_dict_to_list(tree)


async def get_file_content(
    skill_uid: str,
    user_uid: str,
    role: str,
    path: str,
    db: AsyncSession,
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    if skill is None:
        raise AppError(
            detail="找不到指定的 Skill",
            response_code=404,
            status_code=404,
        )

    if role != "admin":
        if str(skill.owner_uid) != user_uid and skill.visibility != "public":
            raise AppError(
                detail="找不到指定的 Skill",
                response_code=404,
                status_code=404,
            )

    zip_path = skill.file_path
    if not Path(zip_path).exists():
        raise AppError(
            detail="檔案不存在，請聯繫管理員",
            response_code=404,
            status_code=404,
        )

    normalized = path.lstrip("/").replace("\\", "/")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            try:
                info = zf.getinfo(normalized)
            except KeyError:
                raise AppError(
                    detail="找不到指定的檔案",
                    response_code=404,
                    status_code=404,
                )

            if info.is_dir():
                raise AppError(
                    detail="指定的路徑為目錄，無法顯示內容",
                    response_code=400,
                    status_code=400,
                )

            size = info.file_size
            if size > FILE_PREVIEW_MAX_BYTES:
                return {
                    "path": normalized,
                    "size": size,
                    "encoding": "text",
                    "content": "",
                    "too_large": True,
                }

            with zf.open(info, "r") as f:
                data = f.read()
    except zipfile.BadZipFile:
        raise AppError(
            detail="檔案格式損毀，無法讀取",
            response_code=500,
            status_code=500,
        )

    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "path": normalized,
            "size": size,
            "encoding": "binary",
            "content": "",
            "too_large": False,
        }

    return {
        "path": normalized,
        "size": size,
        "encoding": "text",
        "content": content,
        "too_large": False,
    }


def _build_tree(
    tree: dict[str, FileTreeNode],
    parts: list[str],
    is_dir: bool,
) -> None:
    if not parts:
        return

    name = parts[0]
    remaining = parts[1:]

    if name not in tree:
        if remaining or is_dir:
            tree[name] = FileTreeNode(name=name, type="directory", children=[])
        else:
            tree[name] = FileTreeNode(name=name, type="file")

    if remaining:
        node = tree[name]
        if node.type == "file":
            node.type = "directory"
            node.children = []
        child_dict: dict[str, FileTreeNode] = {}
        if node.children:
            for child in node.children:
                child_dict[child.name] = child
        _build_tree(child_dict, remaining, is_dir)
        node.children = _tree_dict_to_list(child_dict)


def _tree_dict_to_list(tree: dict[str, FileTreeNode]) -> list[FileTreeNode]:
    dirs = sorted(
        [n for n in tree.values() if n.type == "directory"],
        key=lambda x: x.name,
    )
    files = sorted(
        [n for n in tree.values() if n.type == "file"],
        key=lambda x: x.name,
    )
    return dirs + files
