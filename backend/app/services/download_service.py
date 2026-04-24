"""下載計數共用 service。

規格（docs/Tasks/v1.2/tasks-v1.2.1.md §3-3）：
- `try_increment_download`：Redis SETNX `download:dedup:{type}:{uid}:{user_uid}` TTL 86400
- SETNX 成功（首次） → 同 transaction UPDATE ... SET download_count += 1，回 True
- Redis 不通 → log warning，仍 +1（fallback 不去重），回 True

呼叫時機：在 StreamingResponse / FileResponse **即將回傳**前（HEAD / 預覽不計）。
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.redis_client import try_setnx_with_ttl
from app.repositories import agent_repository, skill_repository

logger = logging.getLogger(__name__)

DEDUP_TTL_SECONDS = 86400


def _dedup_key(resource_type: str, resource_uid: str, user_uid: str) -> str:
    return f"download:dedup:{resource_type}:{resource_uid}:{user_uid}"


async def _increment_by_type(
    resource_type: str, resource_uid: str, db: AsyncSession
) -> int | None:
    if resource_type == "agent":
        return await agent_repository.increment_download_count(
            resource_uid, 1, db
        )
    if resource_type == "skill":
        return await skill_repository.increment_download_count(
            resource_uid, 1, db
        )
    # script v1.2.3 才導入
    logger.warning(
        "try_increment_download 遇到未支援的 resource_type：%s", resource_type
    )
    return None


async def try_increment_download(
    resource_type: str,
    resource_uid: str,
    user_uid: str,
    db: AsyncSession,
) -> bool:
    """嘗試計數；回傳是否實際執行了 +1（True = 已計；False = dedup 命中未計）。

    - Redis 首次 SETNX 成功 → +1，回 True
    - Redis 已有 key（24h 內已下載）→ 不 +1，回 False
    - Redis 不通（None）→ fallback +1（不去重），回 True
    """
    key = _dedup_key(resource_type, resource_uid, user_uid)
    setnx_result = await try_setnx_with_ttl(key, DEDUP_TTL_SECONDS)

    if setnx_result is True:
        # 首次 → 計數
        await _increment_by_type(resource_type, resource_uid, db)
        return True

    if setnx_result is False:
        # 命中 dedup → 不計
        return False

    # None → Redis 不通 fallback
    logger.warning(
        "Redis 不通，下載計數走 fallback（不去重）：type=%s uid=%s",
        resource_type,
        resource_uid,
    )
    await _increment_by_type(resource_type, resource_uid, db)
    return True
