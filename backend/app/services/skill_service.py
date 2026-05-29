import io
import logging
import mimetypes
import os
import uuid
import zipfile

from botocore.exceptions import ClientError
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
    entity_tag_repository,
    skill_repository,
    user_favorite_repository,
)
from app.schemas.common import VisibilityRequest
from app.schemas.skills.schemas import FileTreeNode, SkillUpdateRequest
from app.schemas.tags.schemas import EntityTagsRequest
from app.services import download_service, tag_service
from app.storage import s3_storage

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

# zip bomb 防線：解壓後總大小不得超過 max_size 的 N 倍
ZIP_BOMB_RATIO = 10


def _check_zip_bomb(zip_content: bytes, max_total_bytes: int) -> None:
    """In-memory 版本：直接驗 bytes, 不再 round trip 寫到 disk。"""
    limit = max_total_bytes * ZIP_BOMB_RATIO
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zf:
            total = sum(info.file_size for info in zf.infolist())
    except zipfile.BadZipFile:
        raise AppError(
            detail="檔案格式損毀，無法讀取",
            response_code=500,
            status_code=500,
        )
    if total > limit:
        raise AppError(
            detail="壓縮後內容異常（疑似 zip bomb），請檢查內容",
            response_code=400,
            status_code=400,
        )


def _skill_to_dict(
    skill: Skill,
    is_favorited: bool = False,
    tags: list[dict] | None = None,
) -> dict:
    return {
        "skill_uid": str(skill.skill_uid),
        "owner_user_uid": str(skill.owner_user_uid),
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
        "tags": tags or [],
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
        # 優先序: 共同根目錄 → 單檔 basename → 多檔平鋪 fallback 才用使用者命名
        original_filename = top_folder or (
            os.path.basename(entries[0][0]) if len(entries) == 1 else name
        )
        zip_content = _build_zip(entries)

    base = os.path.splitext(os.path.basename(original_filename))[0] or name

    # zip bomb 偵測：使用者可能直接上傳 .zip 檔，需擋住極高壓縮比
    _check_zip_bomb(zip_content, max_size)

    key = s3_storage.build_key("skills", skill_uid, f"{base}.zip")
    try:
        await s3_storage.put_object(key, zip_content, "application/zip")
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
            "owner_user_uid": user_uid,
            "name": name,
            "description": description,
            "storage_key": key,
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
    tag_map = await entity_tag_repository.get_tags_bulk(
        "skill", [skill_uid], db
    )
    return _skill_to_dict(
        skill,
        is_favorited=skill_uid in favorited,
        tags=tag_map.get(skill_uid, []),
    )


async def list_skills(
    user_uid: str,
    cursor: str | None,
    limit: int,
    db: AsyncSession,
    order_by: str | None = None,
    order: str = "desc",
    tag_uids: list[str] | None = None,
) -> dict:
    base_stmt = skill_repository.stmt_visible_to_user(user_uid)
    base_stmt = entity_tag_repository.apply_tag_filter(
        base_stmt, "skill", Skill.skill_uid, tag_uids
    )

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
    tag_map = await entity_tag_repository.get_tags_bulk(
        "skill", item_uids, db
    )
    return {
        "items": [
            _skill_to_dict(
                s,
                is_favorited=str(s.skill_uid) in favorited_set,
                tags=tag_map.get(str(s.skill_uid), []),
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

    await skill_repository.update_obj(skill, update_data, db)
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "skill", [skill_uid], db
    )
    tag_map = await entity_tag_repository.get_tags_bulk(
        "skill", [skill_uid], db
    )
    return _skill_to_dict(
        skill,
        is_favorited=skill_uid in favorited,
        tags=tag_map.get(skill_uid, []),
    )


async def set_tags(
    skill_uid: str,
    user_uid: str,
    role: str,
    data: EntityTagsRequest,
    db: AsyncSession,
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_modifiable(skill, user_uid, role, NOT_FOUND_DETAIL)
    assert skill is not None

    target_uids = await tag_service.resolve_tag_uids(
        user_uid, data.names, data.tag_uids, db
    )
    await entity_tag_repository.set_entity_tags(
        "skill", skill_uid, target_uids, db
    )

    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "skill", [skill_uid], db
    )
    tag_map = await entity_tag_repository.get_tags_bulk(
        "skill", [skill_uid], db
    )
    return _skill_to_dict(
        skill,
        is_favorited=skill_uid in favorited,
        tags=tag_map.get(skill_uid, []),
    )


async def delete_skill(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> None:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_owner(
        skill, user_uid, NOT_FOUND_DETAIL, "只有擁有者可以刪除 Skill"
    )
    assert skill is not None
    await skill_repository.soft_delete(skill, db)

    try:
        await s3_storage.mark_deleted(skill.storage_key)
    except Exception:
        logger.warning(
            "mark_deleted 失敗 key=%s", skill.storage_key, exc_info=True
        )


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
    await skill_repository.update_obj(skill, {"visibility": data.visibility}, db)
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "skill", [skill_uid], db
    )
    return _skill_to_dict(skill, is_favorited=skill_uid in favorited)


async def download_skill(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> tuple[bytes, str]:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_readable(skill, user_uid, role, NOT_FOUND_DETAIL)
    assert skill is not None

    try:
        data = await s3_storage.get_object(skill.storage_key)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise AppError(
                detail="檔案不存在，請聯繫管理員",
                response_code=404,
                status_code=404,
            )
        raise

    # StreamingResponse / FileResponse 即將回傳前才 +1（且同 user 24h Redis dedup）
    counted = await download_service.try_increment_download(
        "skill", skill_uid, user_uid, db
    )
    # 下載人員紀錄：每次下載都記一筆（與 24h dedup 計數獨立）
    await download_service.record_download(
        "skill", skill_uid, skill.name, user_uid, counted, db
    )

    download_name = f"{os.path.splitext(skill.original_filename)[0]}.zip"
    return data, download_name


async def get_file_tree(
    skill_uid: str, user_uid: str, role: str, db: AsyncSession
) -> list[FileTreeNode]:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_readable(skill, user_uid, role, NOT_FOUND_DETAIL)
    assert skill is not None

    try:
        data = await s3_storage.get_object(skill.storage_key)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise AppError(
                detail="檔案不存在，請聯繫管理員",
                response_code=404,
                status_code=404,
            )
        raise

    tree: dict[str, FileTreeNode] = {}

    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
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

    try:
        zip_bytes = await s3_storage.get_object(skill.storage_key)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise AppError(
                detail="檔案不存在，請聯繫管理員",
                response_code=404,
                status_code=404,
            )
        raise

    normalized = path.lstrip("/").replace("\\", "/")

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
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
    ensure_owner(skill, user_uid, NOT_FOUND_DETAIL, "只有擁有者可以重新上傳 Skill")
    assert skill is not None
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
        # 優先序: 共同根目錄 → 單檔 basename → 多檔平鋪 fallback 才用 skill.name
        original_filename = top_folder or (
            os.path.basename(entries[0][0])
            if len(entries) == 1
            else skill.name
        )
        zip_content = _build_zip(entries)

    # zip bomb 偵測：reupload 同樣可能塞入惡意 zip
    _check_zip_bomb(zip_content, max_size)

    # 決策 #13：filename 變動 → 新 key put + 舊 key mark_deleted；
    # filename 不變 → 同 key 覆蓋（bucket versioning 自動保留歷史）
    base = os.path.splitext(os.path.basename(original_filename))[0] or skill.name
    new_key = s3_storage.build_key("skills", skill_uid, f"{base}.zip")
    old_key = skill.storage_key

    try:
        await s3_storage.put_object(new_key, zip_content, "application/zip")
    except Exception:
        logger.exception("檔案儲存失敗")
        raise AppError(
            detail="檔案儲存失敗，請稍後再試",
            response_code=500,
            status_code=500,
        )

    if new_key != old_key:
        try:
            await s3_storage.mark_deleted(old_key)
        except Exception:
            logger.warning(
                "舊 key mark_deleted 失敗 key=%s", old_key, exc_info=True
            )

    await skill_repository.update_obj(
        skill,
        {
            "storage_key": new_key,
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
    zip_bytes: bytes,
    target_path: str,
    new_content: bytes,
) -> bytes:
    """讀原 zip bytes → 重建一份 zip bytes 並替換 target_path 內容。回傳新 zip bytes。"""
    buf = io.BytesIO()
    try:
        found = False
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as src, zipfile.ZipFile(
            buf, "w", zipfile.ZIP_DEFLATED
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
    except zipfile.BadZipFile:
        raise AppError(
            detail="檔案格式損毀，無法讀取",
            response_code=500,
            status_code=500,
        )

    return buf.getvalue()


async def update_file_content(
    skill_uid: str,
    user_uid: str,
    path: str,
    content: str,
    expected_updated_at: str,
    db: AsyncSession,
) -> dict:
    skill = await skill_repository.get_by_uid(skill_uid, db)
    ensure_owner(skill, user_uid, NOT_FOUND_DETAIL, "只有擁有者可以編輯 Skill 檔案")
    assert skill is not None
    _check_optimistic_lock(skill, expected_updated_at)

    normalized = path.lstrip("/").replace("\\", "/").strip()
    if not normalized:
        raise AppError(
            detail="檔案路徑不可為空", response_code=400, status_code=400
        )
    # 防 zip-slip：路徑段不可含 `..` 或空段（雖目前未解壓到磁碟，但避免未來下載解壓時逸出）
    if any(p in ("..", "") for p in normalized.split("/")):
        raise AppError(
            detail=f"不允許的路徑：{path}",
            response_code=400,
            status_code=400,
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

    try:
        zip_bytes = await s3_storage.get_object(skill.storage_key)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise AppError(
                detail="檔案不存在，請聯繫管理員",
                response_code=404,
                status_code=404,
            )
        raise

    new_zip = _rebuild_zip_with_replacement(zip_bytes, normalized, encoded)

    # 決策 #13：同 key 覆蓋（bucket versioning 自動保留歷史）
    try:
        await s3_storage.put_object(
            skill.storage_key, new_zip, "application/zip"
        )
    except Exception:
        logger.exception("檔案儲存失敗")
        raise AppError(
            detail="檔案儲存失敗，請稍後再試",
            response_code=500,
            status_code=500,
        )

    await skill_repository.update_obj(skill, {"file_size": len(new_zip)}, db)

    return {
        "file_path": normalized,
        "size": len(encoded),
        "updated_at": to_taipei_iso(skill.updated_at),
        "new_content_preview": content[:200],
    }
