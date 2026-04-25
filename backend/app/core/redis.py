import logging
import re

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_clients: dict[int, aioredis.Redis] = {}


def _build_redis_url(db: int) -> str:
    """組指定 db 的 Redis URL；若 REDIS_URL 已設則覆寫其末段 db 索引。"""
    if settings.REDIS_URL:
        return re.sub(r"/\d+(?=\?|$)", f"/{db}", settings.REDIS_URL)
    return f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{db}"


async def init_redis() -> None:
    """初始化預設 db client（`settings.REDIS_DB`）並 ping；其餘 db 走 lazy。"""
    default_db = settings.REDIS_DB
    _clients[default_db] = aioredis.from_url(
        _build_redis_url(default_db), decode_responses=True
    )
    try:
        await _clients[default_db].ping()
        logger.info("Redis 連線成功（預設 db=%d）", default_db)
    except Exception as exc:
        # 不 raise：fallback 由後續呼叫端（如下載計數）處理
        logger.warning(
            "Redis ping 失敗，後續依賴 Redis 的功能將走 fallback：%s", exc
        )


async def close_redis() -> None:
    for db, client in list(_clients.items()):
        try:
            await client.aclose()
        except Exception:
            pass
        _clients.pop(db, None)


def get_redis(db: int | None = None) -> aioredis.Redis:
    """取得指定 db 的 Redis client；未指定時走 `settings.REDIS_DB`。

    首次對某 db 呼叫時 lazy 建立 client；之後快取重用。
    """
    if not _clients:
        raise RuntimeError("Redis 尚未初始化（請於 lifespan 呼叫 init_redis）")

    target_db = settings.REDIS_DB if db is None else db
    if target_db not in _clients:
        _clients[target_db] = aioredis.from_url(
            _build_redis_url(target_db), decode_responses=True
        )
    return _clients[target_db]
