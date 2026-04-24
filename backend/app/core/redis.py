import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

redis_client: aioredis.Redis | None = None


def _build_redis_url() -> str:
    """優先使用既有 REDIS_URL；否則以 REDIS_HOST/PORT/DB 組合。"""
    if settings.REDIS_URL:
        return settings.REDIS_URL
    return f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"


async def init_redis() -> None:
    global redis_client
    redis_client = aioredis.from_url(
        _build_redis_url(),
        decode_responses=True,
    )
    try:
        await redis_client.ping()
        logger.info("Redis 連線成功")
    except Exception as exc:
        # 不 raise：fallback 由後續呼叫端（如下載計數）處理
        logger.warning("Redis ping 失敗，後續依賴 Redis 的功能將走 fallback：%s", exc)


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


def get_redis() -> aioredis.Redis:
    if redis_client is None:
        raise RuntimeError("Redis 尚未初始化")
    return redis_client
