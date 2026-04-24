"""Redis 用戶端封裝（依賴注入入口）。

規格（docs/Tasks/v1.2/tasks-v1.2.1.md §0-2）：
- `get_redis()` 作為 FastAPI 依賴注入點
- lifespan 啟動時做 ping（見 `app.core.redis.init_redis`）
- 下載 dedup 等功能呼叫 `try_setnx_with_ttl` 封裝，Redis 不通時自動 fallback
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.core.redis import get_redis as _core_get_redis

logger = logging.getLogger(__name__)


def get_redis() -> aioredis.Redis:
    """取得全域 Redis 連線（於 lifespan 初始化）。"""
    return _core_get_redis()


async def try_setnx_with_ttl(key: str, ttl_seconds: int) -> bool | None:
    """嘗試 SETNX + 設 TTL。

    回傳：
    - True  → 首次設定成功（尚未存在）
    - False → 已存在（重複請求）
    - None  → Redis 不通 / 其他錯誤（呼叫端自行決定 fallback）
    """
    try:
        client = get_redis()
        # NX + EX 一步完成：避免 TTL 漏設的競態
        ok = await client.set(name=key, value="1", ex=ttl_seconds, nx=True)
        return bool(ok)
    except Exception as exc:
        logger.warning("Redis SETNX 失敗（key=%s）：%s", key, exc)
        return None
