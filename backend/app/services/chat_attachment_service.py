import base64
import logging
import mimetypes
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.models.chat_attachment import ChatAttachment
from app.repositories import (
    chat_attachment_repository,
    chat_session_repository,
)
from app.services import system_setting_service

logger = logging.getLogger(__name__)

DEFAULT_MAX_SIZE_MB = 10
HARD_MAX_SIZE_MB = 50
DEFAULT_MAX_PER_MESSAGE = 5
HARD_MAX_PER_MESSAGE = 10
DEFAULT_ALLOWED_EXTS = (
    ".png,.jpg,.jpeg,.webp,.pdf,.md,.txt,.json,.csv"
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
TEXT_EXTS = {".md", ".txt", ".json", ".csv"}
PDF_EXTS = {".pdf"}

SESSION_NOT_FOUND = "找不到指定的 Session 或無權存取"
ATTACHMENT_NOT_FOUND = "找不到指定的附件或無權存取"


def _to_dict(attachment: ChatAttachment) -> dict:
    return {
        "chat_attachment_uid": str(attachment.chat_attachment_uid),
        "chat_session_uid": str(attachment.chat_session_uid),
        "file_name": attachment.file_name,
        "file_type": attachment.file_type,
        "file_size": attachment.file_size,
        "created_at": to_taipei_iso(attachment.created_at),
    }


def _ext_of(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


async def _load_limits(db: AsyncSession) -> tuple[int, int, set[str]]:
    size_mb = await system_setting_service.get_int(
        "chat.max_attachment_size_mb", DEFAULT_MAX_SIZE_MB, db
    )
    size_mb = max(1, min(size_mb, HARD_MAX_SIZE_MB))

    max_per_msg = await system_setting_service.get_int(
        "chat.max_attachments_per_message", DEFAULT_MAX_PER_MESSAGE, db
    )
    max_per_msg = max(1, min(max_per_msg, HARD_MAX_PER_MESSAGE))

    allowed_raw = await system_setting_service.get(
        "chat.attachment_allowed_extensions", DEFAULT_ALLOWED_EXTS, db
    )
    allowed_raw = allowed_raw or DEFAULT_ALLOWED_EXTS
    allowed = {
        s.strip().lower()
        for s in allowed_raw.split(",")
        if s.strip()
    }
    return size_mb, max_per_msg, allowed


async def upload_attachments(
    user_uid: str,
    session_uid: str,
    files: list[UploadFile],
    db: AsyncSession,
) -> list[dict]:
    """驗證 session 擁有權、白名單、大小、每訊息數量，寫檔 + DB。"""
    if not files:
        raise AppError(
            detail="請至少選擇一個檔案", response_code=400, status_code=400
        )

    session = await chat_session_repository.get_by_uid(session_uid, db)
    if session is None or str(session.owner_user_uid) != user_uid:
        raise AppError(
            detail=SESSION_NOT_FOUND, response_code=404, status_code=404
        )

    size_mb, max_per_msg, allowed_exts = await _load_limits(db)
    max_bytes = size_mb * 1024 * 1024

    if len(files) > max_per_msg:
        raise AppError(
            detail=f"單則訊息最多 {max_per_msg} 個附件",
            response_code=400,
            status_code=400,
        )

    # 讀取 + 驗證（全部驗完才寫 DB / 檔案）
    staged: list[tuple[UploadFile, bytes, str, str]] = []
    for uf in files:
        filename = uf.filename or ""
        ext = _ext_of(filename)
        if not ext or ext not in allowed_exts:
            raise AppError(
                detail=(
                    f"不允許的檔案類型：{filename}（允許：{','.join(sorted(allowed_exts))}）"
                ),
                response_code=400,
                status_code=400,
            )

        content = await uf.read()
        if len(content) == 0:
            raise AppError(
                detail=f"檔案內容為空：{filename}",
                response_code=400,
                status_code=400,
            )
        if len(content) > max_bytes:
            raise AppError(
                detail=f"檔案超過大小上限 {size_mb} MB：{filename}",
                response_code=400,
                status_code=400,
            )

        mime = uf.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        staged.append((uf, content, ext, mime))

    # 儲存 + 建 DB record
    ym = datetime.now().strftime("%Y%m")
    base_dir = Path(settings.ATTACHMENTS_UPLOAD_DIR) / ym
    base_dir.mkdir(parents=True, exist_ok=True)

    created: list[ChatAttachment] = []
    for uf, content, ext, mime in staged:
        attachment_uid = uuid.uuid4()
        file_path = base_dir / f"{attachment_uid}{ext}"
        try:
            file_path.write_bytes(content)
        except Exception:
            logger.exception("附件寫檔失敗 %s", file_path)
            raise AppError(
                detail="附件儲存失敗，請稍後再試",
                response_code=500,
                status_code=500,
            )

        attachment = await chat_attachment_repository.create(
            {
                "chat_attachment_uid": attachment_uid,
                "owner_user_uid": user_uid,
                "chat_session_uid": session_uid,
                "file_name": uf.filename or f"{attachment_uid}{ext}",
                "file_type": mime,
                "file_size": len(content),
                "file_path": str(file_path),
            },
            db,
        )
        created.append(attachment)

    await db.commit()
    return [_to_dict(a) for a in created]


async def get_attachment_content(
    attachment_uid: str,
    user_uid: str,
    db: AsyncSession,
) -> tuple[bytes, str, str]:
    """下載 / 預覽：只有 session owner 可取，其他人 403。回傳 (bytes, mime, file_name)。"""
    attachment = await chat_attachment_repository.get_by_uid(attachment_uid, db)
    if attachment is None:
        raise AppError(
            detail=ATTACHMENT_NOT_FOUND, response_code=404, status_code=404
        )

    session = await chat_session_repository.get_by_uid(
        str(attachment.chat_session_uid), db
    )
    if session is None or str(session.owner_user_uid) != user_uid:
        # 非 session 擁有者 → 403（對齊 task 決策 #8）
        raise AppError(
            detail="無權存取此附件", response_code=403, status_code=403
        )

    file_path = Path(attachment.file_path)
    if not file_path.exists():
        raise AppError(
            detail="附件檔案不存在，請聯繫管理員",
            response_code=404,
            status_code=404,
        )
    try:
        data = file_path.read_bytes()
    except Exception:
        logger.exception("讀取附件失敗 %s", file_path)
        raise AppError(
            detail="讀取附件失敗，請稍後再試",
            response_code=500,
            status_code=500,
        )
    return data, attachment.file_type, attachment.file_name


def _decode_text(content: bytes) -> tuple[str, bool]:
    """UTF-8 優先，失敗回退 latin-1 並設 fallback 旗標。"""
    try:
        return content.decode("utf-8"), False
    except UnicodeDecodeError:
        return content.decode("latin-1", errors="replace"), True


async def load_for_prompt(
    attachment_uids: list[str],
    user_uid: str,
    session_uid: str,
    db: AsyncSession,
) -> list[dict]:
    """
    將附件內容讀進記憶體供 chat_service 組 prompt 使用。

    回傳每個附件：
      - kind: "image" | "text" | "pdf"
      - uid / file_name / file_type
      - content_b64: 圖片用 base64 data URL；其他則 None
      - content_text: 文字檔用讀出的字串；其他則 None
      - text_fallback_latin1: 文字檔是否走 latin-1 fallback
    """
    if not attachment_uids:
        return []

    attachments = await chat_attachment_repository.list_by_uids(
        attachment_uids, db
    )
    # 驗證：附件必須屬於同一 session 且該 session 擁有者是當前使用者
    session = await chat_session_repository.get_by_uid(session_uid, db)
    if session is None or str(session.owner_user_uid) != user_uid:
        raise AppError(
            detail=SESSION_NOT_FOUND, response_code=404, status_code=404
        )

    loaded: list[dict] = []
    for attachment in attachments:
        if str(attachment.chat_session_uid) != session_uid:
            # 避免跨 session 夾帶他人附件
            continue

        ext = _ext_of(attachment.file_name)
        file_path = Path(attachment.file_path)
        if not file_path.exists():
            logger.warning(
                "附件檔案不存在，略過 uid=%s path=%s",
                attachment.chat_attachment_uid,
                file_path,
            )
            continue

        try:
            raw = file_path.read_bytes()
        except Exception:
            logger.exception(
                "讀附件失敗 uid=%s", attachment.chat_attachment_uid
            )
            continue

        entry: dict = {
            "uid": str(attachment.chat_attachment_uid),
            "file_name": attachment.file_name,
            "file_type": attachment.file_type,
            "content_b64": None,
            "content_text": None,
            "text_fallback_latin1": False,
            "kind": "other",
        }

        if ext in IMAGE_EXTS:
            mime = attachment.file_type or "image/png"
            b64 = base64.b64encode(raw).decode("ascii")
            entry["content_b64"] = f"data:{mime};base64,{b64}"
            entry["kind"] = "image"
        elif ext in TEXT_EXTS:
            text, fallback = _decode_text(raw)
            entry["content_text"] = text
            entry["text_fallback_latin1"] = fallback
            entry["kind"] = "text"
        elif ext in PDF_EXTS:
            # v1.1.6 僅附件登記，不抽 PDF 內文
            entry["kind"] = "pdf"
        loaded.append(entry)

    return loaded


async def list_by_session_summary(
    session_uid: str, db: AsyncSession
) -> list[dict]:
    items = await chat_attachment_repository.list_by_session(session_uid, db)
    return [_to_dict(a) for a in items]


async def get_summary_map_by_uids(
    attachment_uids: list[str], db: AsyncSession
) -> dict[str, dict]:
    """批次撈附件摘要（給 ChatMessageResponse.attachments 填充，避免 N+1）。"""
    if not attachment_uids:
        return {}
    items = await chat_attachment_repository.list_by_uids(
        attachment_uids, db
    )
    return {str(a.chat_attachment_uid): _to_dict(a) for a in items}
