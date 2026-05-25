"""Script（腳本資源）服務層。

規格：docs/Tasks/v1.2/tasks-v1.2.3.md §A-5 / propose-v1.2.0.md §2-3

與 Skill 差異：
- 無 visibility 欄位（v1.2 全為 owner-only；跨使用者可見性留 v1.4）
- 副檔名白名單 + 檔案數量 + 總大小 + zip bomb 四重安全閘
- 打包後統一以 zip 儲存（sub path 保留使用者原始目錄結構）
"""

from __future__ import annotations

import io
import logging
import os
import uuid
import zipfile

from botocore.exceptions import ClientError
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ensure_modifiable, ensure_owner, ensure_readable
from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.core.pagination import paginate, paginate_ordered
from app.models.script import Script
from app.repositories import (
    script_repository,
    user_favorite_repository,
)
from app.schemas.scripts.schemas import ScriptUpdateRequest
from app.services import download_service, system_setting_service
from app.storage import s3_storage

logger = logging.getLogger(__name__)

NOT_FOUND_DETAIL = "找不到指定的 Script"

# 預設值（若 system_setting 未設時 fallback）
_DEFAULT_MAX_TOTAL_SIZE_MB = 50
_DEFAULT_MAX_FILES = 200
_DEFAULT_ALLOWED_EXTS = (
    ".py,.sh,.js,.ts,.json,.yaml,.yml,.md,.txt,.csv"
)

# 硬上限（設定值不得超過）
_HARD_MAX_TOTAL_SIZE_MB = 200
_HARD_MAX_FILES = 1000


def _script_to_dict(script: Script, is_favorited: bool = False) -> dict:
    return {
        "script_uid": str(script.script_uid),
        "owner_user_uid": str(script.owner_user_uid),
        "owner_username": script.owner.username if script.owner else None,
        "name": script.name,
        "description": script.description,
        "file_name": script.file_name,
        "file_size": script.file_size,
        "visibility": script.visibility,
        "is_active": script.is_active,
        "favorite_count": script.favorite_count,
        "download_count": script.download_count,
        "is_favorited": is_favorited,
        "created_at": to_taipei_iso(script.created_at),
        "updated_at": to_taipei_iso(script.updated_at),
    }


def _validate_relative_path(rel_path: str) -> str:
    normalized = rel_path.replace("\\", "/").strip()
    if not normalized:
        raise AppError(
            detail="檔案路徑不可為空", response_code=400, status_code=400
        )
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


async def _load_upload_settings(db: AsyncSession) -> tuple[int, int, list[str]]:
    """讀取 system_setting 的 Script 上傳限制；套用硬上限。

    回傳：`(max_total_bytes, max_files, allowed_extensions)`
    """
    max_mb_raw = await system_setting_service.get_int(
        "script.max_total_size_mb", _DEFAULT_MAX_TOTAL_SIZE_MB, db
    )
    max_files_raw = await system_setting_service.get_int(
        "script.max_files_per_upload", _DEFAULT_MAX_FILES, db
    )
    allowed_raw = await system_setting_service.get(
        "script.allowed_extensions", _DEFAULT_ALLOWED_EXTS, db
    )

    max_mb = max(1, min(int(max_mb_raw), _HARD_MAX_TOTAL_SIZE_MB))
    max_files = max(1, min(int(max_files_raw), _HARD_MAX_FILES))
    exts = [
        e.strip().lower() for e in (allowed_raw or "").split(",") if e.strip()
    ]
    # 副檔名規範化：確保以 . 起頭
    normalized_exts = [e if e.startswith(".") else f".{e}" for e in exts]
    if not normalized_exts:
        normalized_exts = [
            e.strip() for e in _DEFAULT_ALLOWED_EXTS.split(",") if e.strip()
        ]

    return max_mb * 1024 * 1024, max_files, normalized_exts


def _check_extension(filename: str, allowed_exts: list[str]) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_exts:
        raise AppError(
            detail=f"不允許的副檔名 {ext or '(無)'}：{filename}",
            response_code=400,
            status_code=400,
        )


async def _read_and_validate_entries(
    files: list[UploadFile],
    relative_paths: list[str],
    max_total_bytes: int,
    max_files: int,
    allowed_exts: list[str],
) -> list[tuple[str, bytes]]:
    """驗證 + 讀取所有上傳檔案到 `[(rel_path, content), ...]`。"""
    if not files:
        raise AppError(
            detail="請至少選擇一個檔案",
            response_code=400,
            status_code=400,
        )
    if len(files) > max_files:
        raise AppError(
            detail=f"檔案數量超過上限（{max_files}）",
            response_code=400,
            status_code=400,
        )
    if len(relative_paths) != len(files):
        raise AppError(
            detail="relative_paths 與 files 數量不一致",
            response_code=400,
            status_code=400,
        )

    entries: list[tuple[str, bytes]] = []
    total_size = 0

    for uf, rel_raw in zip(files, relative_paths, strict=True):
        rel_path = _validate_relative_path(rel_raw or uf.filename or "")
        _check_extension(rel_path, allowed_exts)

        content = await uf.read()
        total_size += len(content)
        if total_size > max_total_bytes:
            raise AppError(
                detail=(
                    f"總檔案大小超過上限（{max_total_bytes // (1024 * 1024)} MB）"
                ),
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

    return entries


def _build_zip(entries: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    try:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel_path, content in entries:
                zf.writestr(rel_path, content)
    except Exception:
        logger.exception("建立 Script ZIP 失敗")
        raise AppError(
            detail="檔案封裝失敗，請稍後再試",
            response_code=500,
            status_code=500,
        )
    return buf.getvalue()


def _check_zip_bomb(zip_bytes: bytes, max_total_bytes: int) -> None:
    """預估解壓後大小 > max_total_bytes * 10 時拒絕。"""
    limit = max_total_bytes * 10
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            total = sum(info.file_size for info in zf.infolist())
    except zipfile.BadZipFile:
        raise AppError(
            detail="檔案格式損毀，無法讀取",
            response_code=500,
            status_code=500,
        )
    if total > limit:
        raise AppError(
            detail=(
                "壓縮後內容異常（疑似 zip bomb），請檢查內容"
            ),
            response_code=400,
            status_code=400,
        )


async def create_script(
    user_uid: str,
    name: str,
    description: str,
    files: list[UploadFile],
    relative_paths: list[str],
    db: AsyncSession,
    visibility: str | None = None,
) -> dict:
    name = (name or "").strip()
    if not name or len(name) > 255:
        raise AppError(
            detail="名稱為必填，且不可超過 255 字元",
            response_code=400,
            status_code=400,
        )

    desc = (description or "").strip()
    if not desc:
        raise AppError(
            detail="描述為必填",
            response_code=400,
            status_code=400,
        )

    if visibility is not None and visibility not in ("public", "private"):
        raise AppError(
            detail="可見性只能為 public 或 private",
            response_code=400,
            status_code=400,
        )

    # 同 owner 名稱不可重複（雖然 DB 也有 partial unique，但先驗證給好錯訊）
    if await script_repository.exists_name_for_owner(user_uid, name, db):
        raise AppError(
            detail=f"已存在同名 Script：{name}",
            response_code=409,
            status_code=409,
        )

    max_total_bytes, max_files, allowed_exts = await _load_upload_settings(db)
    entries = await _read_and_validate_entries(
        files, relative_paths, max_total_bytes, max_files, allowed_exts
    )

    script_uid = uuid.uuid4()

    paths = [p for p, _ in entries]
    top_folder = _common_top_folder(paths)
    file_name = top_folder or (
        os.path.basename(entries[0][0]) if len(entries) == 1 else name
    )

    zip_content = _build_zip(entries)

    # zip bomb 檢測（in-memory）
    _check_zip_bomb(zip_content, max_total_bytes)

    base = os.path.splitext(os.path.basename(file_name))[0] or name
    key = s3_storage.build_key("scripts", script_uid, f"{base}.zip")
    try:
        await s3_storage.put_object(key, zip_content, "application/zip")
    except Exception:
        logger.exception("Script 檔案儲存失敗")
        raise AppError(
            detail="檔案儲存失敗，請稍後再試",
            response_code=500,
            status_code=500,
        )

    script_data: dict = {
        "script_uid": script_uid,
        "owner_user_uid": user_uid,
        "name": name,
        "description": desc,
        "file_name": file_name,
        "storage_key": key,
        "file_size": len(zip_content),
    }
    if visibility is not None:
        script_data["visibility"] = visibility

    script = await script_repository.create(script_data, db)

    return _script_to_dict(script)


async def list_scripts(
    user_uid: str,
    cursor: str | None,
    limit: int,
    db: AsyncSession,
    order_by: str | None = None,
    order: str = "desc",
) -> dict:
    base_stmt = script_repository.stmt_owned_by_user(user_uid)

    if order_by is not None:
        try:
            order_col = script_repository.get_order_column(order_by)
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

    item_uids = [str(s.script_uid) for s in page.items]
    favorited_set = await user_favorite_repository.is_favorited_bulk(
        user_uid, "script", item_uids, db
    )
    return {
        "items": [
            _script_to_dict(
                s, is_favorited=str(s.script_uid) in favorited_set
            )
            for s in page.items
        ],
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def list_public_scripts(
    user_uid: str,
    cursor: str | None,
    limit: int,
    db: AsyncSession,
    order_by: str | None = None,
    order: str = "desc",
) -> dict:
    """列出所有公開（visibility='public'）的 Script。

    v1.2.5 新增：搭配 Dashboard 公開 Scripts 頁籤 / `/api/v1/scripts/public`。
    `is_favorited` 依 current user 折算；排序白名單與 `list_scripts` 一致。
    """
    base_stmt = script_repository.stmt_public()

    if order_by is not None:
        try:
            order_col = script_repository.get_order_column(order_by)
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

    item_uids = [str(s.script_uid) for s in page.items]
    favorited_set = await user_favorite_repository.is_favorited_bulk(
        user_uid, "script", item_uids, db
    )
    return {
        "items": [
            _script_to_dict(
                s, is_favorited=str(s.script_uid) in favorited_set
            )
            for s in page.items
        ],
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def get_script(
    script_uid: str, user_uid: str, role: str, db: AsyncSession
) -> dict:
    script = await script_repository.get_by_uid(script_uid, db)
    ensure_readable(script, user_uid, role, NOT_FOUND_DETAIL)
    assert script is not None
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "script", [script_uid], db
    )
    return _script_to_dict(script, is_favorited=script_uid in favorited)


async def update_script(
    script_uid: str,
    user_uid: str,
    role: str,
    data: ScriptUpdateRequest,
    db: AsyncSession,
) -> dict:
    script = await script_repository.get_by_uid(script_uid, db)
    ensure_modifiable(script, user_uid, role, NOT_FOUND_DETAIL)
    assert script is not None

    update_data: dict = {}
    if data.name is not None:
        # 同 owner 名稱重複檢查（排除自己）；admin 代改時須以實際擁有者查重
        if await script_repository.exists_name_for_owner(
            str(script.owner_user_uid),
            data.name,
            db,
            exclude_script_uid=script_uid,
        ):
            raise AppError(
                detail=f"已存在同名 Script：{data.name}",
                response_code=409,
                status_code=409,
            )
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description
    if data.visibility is not None:
        update_data["visibility"] = data.visibility

    if not update_data:
        raise AppError(
            detail="未提供任何更新欄位",
            response_code=400,
            status_code=400,
        )

    await script_repository.update_obj(script, update_data, db)
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "script", [script_uid], db
    )
    return _script_to_dict(script, is_favorited=script_uid in favorited)


async def soft_delete_script(
    script_uid: str, user_uid: str, role: str, db: AsyncSession
) -> None:
    script = await script_repository.get_by_uid(script_uid, db)
    ensure_owner(script, user_uid, NOT_FOUND_DETAIL, "權限不足")
    assert script is not None
    await script_repository.soft_delete(script, db)
    try:
        await s3_storage.mark_deleted(script.storage_key)
    except Exception:
        logger.warning(
            "mark_deleted 失敗 key=%s", script.storage_key, exc_info=True
        )


async def download_script(
    script_uid: str, user_uid: str, role: str, db: AsyncSession
) -> tuple[bytes, str]:
    script = await script_repository.get_by_uid(script_uid, db)
    ensure_readable(script, user_uid, role, NOT_FOUND_DETAIL)
    assert script is not None

    try:
        data = await s3_storage.get_object(script.storage_key)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise AppError(
                detail="檔案不存在，請聯繫管理員",
                response_code=404,
                status_code=404,
            )
        raise

    # StreamingResponse / FileResponse 即將回傳前才 +1（24h Redis dedup）
    await download_service.try_increment_download(
        "script", script_uid, user_uid, db
    )

    base = os.path.splitext(os.path.basename(script.file_name))[0] or script.name
    download_name = f"{base}.zip"
    return data, download_name
