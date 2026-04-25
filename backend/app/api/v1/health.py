import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.queue_keys import (
    MEMORY_DLQ_KEY,
    MEMORY_QUEUE_KEY,
    PROJECT_MEMORY_DLQ_KEY,
    PROJECT_MEMORY_QUEUE_KEY,
    USER_MEMORY_DLQ_KEY,
    USER_MEMORY_QUEUE_KEY,
)
from app.core.redis import get_redis
from app.core.response import failure, success
from app.schemas.response import ApiResponse, HealthData

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=ApiResponse[HealthData])
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    db_ok = False
    redis_ok = False
    memory_queue_len: int | None = None
    memory_dlq_len: int | None = None
    project_memory_queue_len: int | None = None
    project_memory_dlq_len: int | None = None
    user_memory_queue_len: int | None = None
    user_memory_dlq_len: int | None = None

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("資料庫健康檢查失敗")

    try:
        redis = get_redis()
        await redis.ping()
        redis_ok = True
    except Exception:
        logger.exception("Redis 健康檢查失敗")

    # v1.3.1 / v1.3.5：4 組 queue / DLQ 長度；任一 LLEN 失敗則該欄位為 None
    if redis_ok:
        async def _safe_llen(key: str) -> int | None:
            try:
                return int(await redis.llen(key))
            except Exception:
                logger.warning("讀取 %s 長度失敗", key)
                return None

        memory_queue_len = await _safe_llen(MEMORY_QUEUE_KEY)
        memory_dlq_len = await _safe_llen(MEMORY_DLQ_KEY)
        project_memory_queue_len = await _safe_llen(PROJECT_MEMORY_QUEUE_KEY)
        project_memory_dlq_len = await _safe_llen(PROJECT_MEMORY_DLQ_KEY)
        user_memory_queue_len = await _safe_llen(USER_MEMORY_QUEUE_KEY)
        user_memory_dlq_len = await _safe_llen(USER_MEMORY_DLQ_KEY)

    status = {
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
        "memory_queue_len": memory_queue_len,
        "memory_dlq_len": memory_dlq_len,
        "project_memory_queue_len": project_memory_queue_len,
        "project_memory_dlq_len": project_memory_dlq_len,
        "user_memory_queue_len": user_memory_queue_len,
        "user_memory_dlq_len": user_memory_dlq_len,
    }

    if db_ok and redis_ok:
        return success(data=status)

    return failure(
        detail="部分服務連線異常",
        response_code=503,
        status_code=503,
    )
