import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.redis import get_redis
from app.core.response import failure, success
from app.schemas.response import ApiResponse, HealthData

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=ApiResponse[HealthData])
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    db_ok = False
    redis_ok = False

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

    status = {
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
    }

    if db_ok and redis_ok:
        return success(data=status)

    return failure(
        detail="部分服務連線異常",
        response_code=503,
        status_code=503,
    )
