"""download_log repository（v1.5.x）。

提供 log()：單筆寫入下載紀錄；寫入失敗僅 log warning 不 raise，
避免稽核資料寫入問題拖垮下載主流程（同 llm_call_log_repository 慣例）。
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.download_log import DownloadLog

logger = logging.getLogger(__name__)


async def log(payload: dict, db: AsyncSession) -> None:
    """單筆寫入下載紀錄；缺漏欄位走 DB DEFAULT。任何 DB 錯誤僅 log，不 raise。"""
    try:
        allowed_fields = {
            "user_uid",
            "username",
            "resource_type",
            "resource_uid",
            "resource_name",
            "counted",
        }
        clean: dict[str, object] = {
            k: v for k, v in (payload or {}).items() if k in allowed_fields
        }
        entity = DownloadLog(**clean)
        db.add(entity)
        await db.flush()
    except Exception as exc:  # 落入稽核自我保護
        logger.warning(
            "download_log 寫入失敗（已忽略，避免拖垮下載主流程）: %s / payload=%s",
            exc,
            payload,
        )
