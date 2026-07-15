"""skill_search_log repository（v1.6.3）。

提供 log()：單筆寫入 AI 查詢稽核紀錄；寫入失敗僅 log warning 不 raise，
避免稽核資料寫入問題拖垮搜尋主流程（同 download_log_repository 慣例）。
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill_search_log import SkillSearchLog

logger = logging.getLogger(__name__)


async def log(payload: dict, db: AsyncSession) -> None:
    """單筆寫入查詢稽核；缺漏欄位走 DB DEFAULT。任何 DB 錯誤僅 log，不 raise。"""
    try:
        allowed_fields = {
            "user_uid",
            "username",
            "query",
            "scope",
            "hit_count",
            "results",
        }
        clean: dict[str, object] = {
            k: v for k, v in (payload or {}).items() if k in allowed_fields
        }
        entity = SkillSearchLog(**clean)
        db.add(entity)
        await db.flush()
    except Exception as exc:  # 稽核自我保護
        logger.warning(
            "skill_search_log 寫入失敗（已忽略，避免拖垮搜尋主流程）: %s / payload=%s",
            exc,
            payload,
        )
