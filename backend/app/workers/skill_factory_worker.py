"""v1.1.7 Skill 工廠 worker：消費 skill_factory_queue，呼叫 analyze_session。"""

import asyncio
import json
import logging
import time

from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis
from app.services import skill_factory_service

logger = logging.getLogger(__name__)

QUEUE_KEY = "skill_factory_queue"
BRPOP_TIMEOUT = 5
MAX_RETRY = 2


async def run() -> None:
    """主迴圈：從 skill_factory_queue 取事件 → analyze_session。失敗記 log 不阻塞。"""
    logger.info("skill_factory_worker 啟動")

    while True:
        try:
            redis = get_redis()
        except RuntimeError:
            await asyncio.sleep(1)
            continue

        try:
            item = await redis.brpop(QUEUE_KEY, timeout=BRPOP_TIMEOUT)
        except asyncio.CancelledError:
            logger.info("skill_factory_worker 收到取消訊號，結束")
            raise
        except Exception as exc:
            logger.warning("skill_factory_worker BRPOP 失敗: %s", exc)
            await asyncio.sleep(2)
            continue

        if item is None:
            continue

        try:
            _, raw = item
            data = json.loads(raw)
            user_uid = data.get("user_uid")
            session_uid = data.get("session_uid")
        except Exception as exc:
            logger.warning("skill_factory_worker 解析 queue item 失敗: %s", exc)
            continue

        if not user_uid or not session_uid:
            logger.warning(
                "skill_factory_worker 收到不完整事件: user_uid=%s session_uid=%s",
                user_uid,
                session_uid,
            )
            continue

        await _handle(user_uid, session_uid)


async def _handle(user_uid: str, session_uid: str) -> None:
    last_err: Exception | None = None
    for attempt in range(MAX_RETRY):
        try:
            async with AsyncSessionLocal() as db:
                await skill_factory_service.analyze_session(
                    session_uid=session_uid,
                    user_uid=user_uid,
                    db=db,
                )
                await db.commit()
            return
        except Exception as exc:
            last_err = exc
            logger.warning(
                "skill_factory_worker 處理失敗 session=%s attempt=%s: %s",
                session_uid,
                attempt + 1,
                exc,
            )
            await asyncio.sleep(1 + attempt)

    logger.exception(
        "skill_factory_worker 重試耗盡 session=%s err=%s",
        session_uid,
        last_err,
    )
    # 本 PoC 不設 DLQ：純失敗只 log，不阻塞其他 session
    _ = time.time()
