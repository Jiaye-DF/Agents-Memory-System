import io
import logging
import mimetypes
import os
import uuid
import zipfile
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ensure_modifiable, ensure_owner, ensure_readable
from app.core.config import settings
from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.core.pagination import paginate, paginate_ordered
from app.models.skill import Skill
from app.repositories import (
    agent_repository,
    skill_repository,
    user_favorite_repository,
)
from app.schemas.common import VisibilityRequest
from app.schemas.skills.schemas import FileTreeNode, SkillUpdateRequest
from app.services import download_service

EDITABLE_EXTENSIONS = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".ts",
    ".js",
    ".sh",
}
FILE_EDIT_MAX_BYTES = 500 * 1024

logger = logging.getLogger(__name__)

BLOCKED_EXTENSIONS = {".exe"}
BLOCKED_MIME_TYPES = {
    "application/x-msdownload",
    "application/x-dosexec",
    "application/x-executable",
}

FILE_PREVIEW_MAX_BYTES = 512 * 1024
NOT_FOUND_DETAIL = "找不到指定的 Skill"


def _skill_to_dict(skill: Skill, is_favorited: bool = False) -> dict:
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
        "favorite_count": skill.favorite_count,
        "download_count": skill.download_count,
        "is_favorited": is_favorited,
        "created_at": to_taipei_iso(skill.created_at),
        "updated_at": to_taipei_iso(skill.updated_at),
    }


def _validate_file(file: UploadFile) -> None:
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext in BLOCKED_EXTENSIONS:
        raise AppError(
            detail=f"不允許上傳 {ext} 檔案：{filename}",
            response_code=400,
            status_code=400,
        )

    content_type = file.content_type or ""
    guessed_type = mimetypes.guess_type(filename)[0] or ""

    if content_type in BLOCKED_MIME_TYPES or guessed_type in BLOCKED_MIME_TYPES:
        raise AppError(
            detail=f"不允許上傳可執行檔案：{filename}",
            response_code=400,
            status_code=400,
        )


def _validate_relative_path(rel_path: str) -> str:
    normalized = rel_path.replace("\\", "/").strip()
    if not normalized:
        raise AppError(detail="檔案路徑不可為空", response_code=400, status_code=400)
    if normalized.startswith("/"):
        raise AppError(
            detail=f"不允許絕對路徑：{rel_path}",
            response_code=400,
            status_code=400,
        )
    parts = normalized.split("/")
    if any(p in ("..", "") for p in parts):
        raise AppError(
            detail=f"不允許的路徑：{rel_path}",
            response_code=400,
            status_code=400,
        )
    return normalized


def _common_top_folder(paths: list[str]) -> str | None:
    if not paths or "/" not in paths[0]:
        return None
    top = paths[0].split("/", 1)[0]
    if all(p == top or p.startswith(f"{top}/") for p in paths):
        return top
    return None


async def upload_skill(
    user_uid: str,
    name: str,
    description: str,
    files: list[UploadFile],
    db: AsyncSession,
) -> dict:
    if not files:
        raise AppError(
            detail="請至少選擇一個檔案",
            response_code=400,
            status_code=400,
        )

    max_size = settings.SKILLS_MAX_FILE_SIZE
    entries: list[tuple[str, bytes]] = []
    total_size = 0

    for uf in files:
        _validate_file(uf)
        rel_path = _validate_relative_path(uf.filename or "")
        content = await uf.read()
        total_size += len(content)
        if total_size > max_size:
            raise AppError(
                detail=f"總檔案大小超過上限（{max_size // (1024 * 1024)} MB）",
                response_code=400,
                status_code=400,
            )
        entries.append((rel_path, content))

    if total_size == 0:
        raise AppError(
            detail="檔案內容為空",
            response_code=400,
            status_code=400,
        )

    is_single_zip = (
        len(entries) == 1 and entries[0][0].lower().endswith(".zip")
    )

    skill_uid = uuid.uuid4()

    if is_single_zip:
        original_filename = entries[0][0]
        zip_content = entries[0][1]
    else:
        paths = [p for p, _ in entries]
        top_folder = _common_top_folder(paths)
        original_filename = top_folder or name
        zip_content = _build_zip(entries)

    skill_dir = Path(settings.SKILLS_UPLOAD_DIR) / str(skill_uid)
    skill_dir.mkdir(parents=True, exist_ok=True)
    base = os.path.splitext(os.path.basename(original_filename))[0] or name
    zip_path = skill_dir / f"{base}.zip"

    try:
        zip_path.write_bytes(zip_content)
    except Exception:
        logger.exception("檔案儲存失敗")
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
            "file_size": len(zip_content),
        },
        db,
    )

    return _skill_to_dict(skill)


async def get_skill(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_readable(skill, user_uid, role, NOT_FOUND_DETAIL)
    assert skill is not None
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "skill", [skill_uid], db
    )
    return _skill_to_dict(skill, is_favorited=skill_uid in favorited)


async def list_skills(
    user_uid: str,
    cursor: str | None,
    limit: int,
    db: AsyncSession,
    order_by: str | None = None,
    order: str = "desc",
) -> dict:
    base_stmt = skill_repository.stmt_visible_to_user(user_uid)

    if order_by is not None:
        try:
            order_col = skill_repository.get_order_column(order_by)
        except ValueError as exc:
            raise AppError(
                detail=str(exc), response_code=400, status_code=400
            ) from exc
        page = await paginate_ordered(
            db,
            base_stmt,
            order_col,
            order_desc=(order.lower() != "asc"),
            cursor=cursor,
            limit=limit,
        )
    else:
        page = await paginate(db, base_stmt, cursor, limit)

    item_uids = [str(s.skill_uid) for s in page.items]
    favorited_set = await user_favorite_repository.is_favorited_bulk(
        user_uid, "skill", item_uids, db
    )
    return {
        "items": [
            _skill_to_dict(
                s, is_favorited=str(s.skill_uid) in favorited_set
            )
            for s in page.items
        ],
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def update_skill(
    skill_uid: str,
    user_uid: str,
    role: str,
    data: SkillUpdateRequest,
    db: AsyncSession,
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_modifiable(skill, user_uid, role, NOT_FOUND_DETAIL)
    assert skill is not None

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
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "skill", [skill_uid], db
    )
    return _skill_to_dict(skill, is_favorited=skill_uid in favorited)


async def delete_skill(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> None:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_owner(
        skill, user_uid, NOT_FOUND_DETAIL, "只有擁有者可以刪除 Skill"
    )
    assert skill is not None
    await skill_repository.soft_delete(skill, db)


async def toggle_visibility(
    skill_uid: str,
    user_uid: str,
    data: VisibilityRequest,
    db: AsyncSession,
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_owner(
        skill, user_uid, NOT_FOUND_DETAIL, "只有擁有者可以切換可見性"
    )
    assert skill is not None
    await skill_repository.update(skill, {"visibility": data.visibility}, db)
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "skill", [skill_uid], db
    )
    return _skill_to_dict(skill, is_favorited=skill_uid in favorited)


async def download_skill(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> tuple[str, str]:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_readable(skill, user_uid, role, NOT_FOUND_DETAIL)
    assert skill is not None

    file_path = skill.file_path
    if not Path(file_path).exists():
        raise AppError(
            detail="檔案不存在，請聯繫管理員",
            response_code=404,
            status_code=404,
        )

    # StreamingResponse / FileResponse 即將回傳前才 +1（且同 user 24h Redis dedup）
    await download_service.try_increment_download(
        "skill", skill_uid, user_uid, db
    )

    download_name = f"{os.path.splitext(skill.original_filename)[0]}.zip"
    return file_path, download_name


async def get_file_tree(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> list[FileTreeNode]:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_readable(skill, user_uid, role, NOT_FOUND_DETAIL)
    assert skill is not None

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
    ensure_readable(skill, user_uid, role, NOT_FOUND_DETAIL)
    assert skill is not None

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


def _build_zip(entries: list[tuple[str, bytes]]) -> bytes:
    """將 `[(rel_path, content), ...]` 打包為 ZIP bytes。"""
    buf = io.BytesIO()
    try:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel_path, content in entries:
                zf.writestr(rel_path, content)
    except Exception:
        logger.exception("建立 ZIP 檔案失敗")
        raise AppError(
            detail="檔案封裝失敗，請稍後再試",
            response_code=500,
            status_code=500,
        )
    return buf.getvalue()


def _ensure_owner_only(
    skill: Skill | None, user_uid: str, action: str
) -> Skill:
    """僅擁有者可操作；admin 也不可代改（resource 不存在回 404）。"""
    if skill is None:
        raise AppError(
            detail=NOT_FOUND_DETAIL, response_code=404, status_code=404
        )
    if str(skill.owner_uid) != user_uid:
        raise AppError(
            detail=f"只有擁有者可以{action}",
            response_code=403,
            status_code=403,
        )
    return skill


def _check_optimistic_lock(skill: Skill, expected_updated_at: str) -> None:
    current = to_taipei_iso(skill.updated_at) or ""
    if current != expected_updated_at:
        raise AppError(
            detail="檔案已被更新，請重新載入後再編輯",
            response_code=409,
            status_code=409,
        )


def _is_editable_filename(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in EDITABLE_EXTENSIONS


async def get_usage(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_readable(skill, user_uid, role, NOT_FOUND_DETAIL)
    assert skill is not None

    agents = await agent_repository.list_by_skill_uid(skill_uid, db)
    items = [
        {
            "agent_uid": str(a.agent_uid),
            "agent_name": a.name,
            "owner_username": a.owner.username if a.owner else None,
            "visibility": a.visibility,
        }
        for a in agents
    ]
    return {"items": items, "count": len(items)}


async def reupload_skill(
    skill_uid: str,
    user_uid: str,
    role: str,
    files: list,
    expected_updated_at: str,
    db: AsyncSession,
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    skill = _ensure_owner_only(skill, user_uid, "重新上傳 Skill")
    _check_optimistic_lock(skill, expected_updated_at)

    if not files:
        raise AppError(
            detail="請至少選擇一個檔案",
            response_code=400,
            status_code=400,
        )

    max_size = settings.SKILLS_MAX_FILE_SIZE
    entries: list[tuple[str, bytes]] = []
    total_size = 0

    for uf in files:
        _validate_file(uf)
        rel_path = _validate_relative_path(uf.filename or "")
        content = await uf.read()
        total_size += len(content)
        if total_size > max_size:
            raise AppError(
                detail=f"總檔案大小超過上限（{max_size // (1024 * 1024)} MB）",
                response_code=400,
                status_code=400,
            )
        entries.append((rel_path, content))

    if total_size == 0:
        raise AppError(
            detail="檔案內容為空",
            response_code=400,
            status_code=400,
        )

    is_single_zip = (
        len(entries) == 1 and entries[0][0].lower().endswith(".zip")
    )

    if is_single_zip:
        original_filename = entries[0][0]
        zip_content = entries[0][1]
    else:
        paths = [p for p, _ in entries]
        top_folder = _common_top_folder(paths)
        original_filename = top_folder or skill.name
        zip_content = _build_zip(entries)

    zip_path = Path(skill.file_path)
    try:
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = zip_path.with_suffix(zip_path.suffix + ".tmp")
        tmp_path.write_bytes(zip_content)
        os.replace(str(tmp_path), str(zip_path))
    except Exception:
        logger.exception("檔案儲存失敗")
        raise AppError(
            detail="檔案儲存失敗，請稍後再試",
            response_code=500,
            status_code=500,
        )

    await skill_repository.update(
        skill,
        {
            "original_filename": original_filename,
            "file_size": len(zip_content),
        },
        db,
    )
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "skill", [skill_uid], db
    )
    return _skill_to_dict(skill, is_favorited=skill_uid in favorited)


def _rebuild_zip_with_replacement(
    zip_path: Path,
    target_path: str,
    new_content: bytes,
) -> int:
    """讀原 zip → 寫臨時 zip 時跳過目標檔 → 寫入新內容 → atomic rename。回傳新 file_size。"""
    tmp_path = zip_path.with_suffix(zip_path.suffix + ".tmp")
    try:
        found = False
        with zipfile.ZipFile(zip_path, "r") as src, zipfile.ZipFile(
            tmp_path, "w", zipfile.ZIP_DEFLATED
        ) as dst:
            for info in src.infolist():
                if info.filename == target_path and not info.is_dir():
                    found = True
                    continue
                dst.writestr(info, src.read(info.filename))
            if not found:
                raise AppError(
                    detail="找不到指定的檔案",
                    response_code=404,
                    status_code=404,
                )
            dst.writestr(target_path, new_content)
    except AppError:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
    except zipfile.BadZipFile:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise AppError(
            detail="檔案格式損毀，無法讀取",
            response_code=500,
            status_code=500,
        )

    os.replace(str(tmp_path), str(zip_path))
    return zip_path.stat().st_size


async def update_file_content(
    skill_uid: str,
    user_uid: str,
    path: str,
    content: str,
    expected_updated_at: str,
    db: AsyncSession,
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    skill = _ensure_owner_only(skill, user_uid, "編輯 Skill 檔案")
    _check_optimistic_lock(skill, expected_updated_at)

    normalized = path.lstrip("/").replace("\\", "/").strip()
    if not normalized:
        raise AppError(
            detail="檔案路徑不可為空", response_code=400, status_code=400
        )

    if not _is_editable_filename(normalized):
        raise AppError(
            detail="此檔案類型不支援線上編輯，請使用『重新上傳整包』",
            response_code=400,
            status_code=400,
        )

    encoded = content.encode("utf-8")
    if len(encoded) > FILE_EDIT_MAX_BYTES:
        raise AppError(
            detail=f"檔案內容超過 {FILE_EDIT_MAX_BYTES // 1024} KB 上限",
            response_code=400,
            status_code=400,
        )

    zip_path = Path(skill.file_path)
    if not zip_path.exists():
        raise AppError(
            detail="檔案不存在，請聯繫管理員",
            response_code=404,
            status_code=404,
        )

    new_size = _rebuild_zip_with_replacement(zip_path, normalized, encoded)

    await skill_repository.update(skill, {"file_size": new_size}, db)

    return {
        "file_path": normalized,
        "size": len(encoded),
        "updated_at": to_taipei_iso(skill.updated_at),
        "new_content_preview": content[:200],
    }
