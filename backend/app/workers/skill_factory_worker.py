"""Agentic Skill 工廠 Worker（v1.3.6）。

消費 `skill_factory_queue`，依 payload 的 `scope` 路由到對應 analyzer：
- scope='session' → analyze_session
- scope='project' → analyze_project
- scope='user'    → analyze_user

向後相容：v1.1.7 PoC payload `{ user_uid, session_uid }`（無 scope）
視為 scope='session' 處理。

失敗策略沿用 v1.1.7：重試 2 次後純 log，不阻塞其他任務。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.database import AsyncSessionLocal
from app.core.redis import get_blocking_redis
from app.services import skill_factory_service

logger = logging.getLogger(__name__)

QUEUE_KEY = "skill_factory_queue"
BRPOP_TIMEOUT = 5
MAX_RETRY = 2


async def run() -> None:
    """主迴圈：從 skill_factory_queue 取事件 → analyze。失敗記 log 不阻塞。"""
    logger.info("skill_factory_worker 啟動（v1.3.6 三 scope 路由）")

    while True:
        try:
            redis = get_blocking_redis()
        except RuntimeError:
            await asyncio.sleep(1)
            continue

        try:
            item = await redis.brpop(QUEUE_KEY, timeout=BRPOP_TIMEOUT)
        except asyncio.CancelledError:
            logger.info("skill_factory_worker 收到取消訊號，結束")
            raise
        except RedisTimeoutError:
            # socket timeout < BRPOP_TIMEOUT 時佇列閒置即逾時，屬 idle 而非錯誤
            continue
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
            # v1.3.6：新欄位 scope / scope_uid；缺則退回 v1.1.7 行為
            scope = data.get("scope") or "session"
            scope_uid = data.get("scope_uid") or data.get("session_uid")
        except Exception as exc:
            logger.warning("skill_factory_worker 解析 queue item 失敗: %s", exc)
            continue

        if not user_uid or not scope_uid:
            logger.warning(
                "skill_factory_worker 收到不完整事件: user_uid=%s scope=%s scope_uid=%s",
                user_uid,
                scope,
                scope_uid,
            )
            continue

        if scope not in ("session", "project", "user"):
            logger.warning(
                "skill_factory_worker 不認識的 scope=%s（user=%s scope_uid=%s）",
                scope,
                user_uid,
                scope_uid,
            )
            continue

        await _handle(scope, scope_uid, user_uid)


async def _handle(scope: str, scope_uid: str, user_uid: str) -> None:
    last_err: Exception | None = None
    for attempt in range(MAX_RETRY):
        try:
            async with AsyncSessionLocal() as db:
                if scope == "session":
                    await skill_factory_service.analyze_session(
                        session_uid=scope_uid,
                        user_uid=user_uid,
                        db=db,
                    )
                elif scope == "project":
                    await skill_factory_service.analyze_project(
                        project_uid=scope_uid,
                        user_uid=user_uid,
                        db=db,
                    )
                else:  # user
                    await skill_factory_service.analyze_user(
                        user_uid=scope_uid,
                        db=db,
                    )
                await db.commit()
            return
        except Exception as exc:
            last_err = exc
            logger.warning(
                "skill_factory_worker 處理失敗 scope=%s scope_uid=%s attempt=%s: %s",
                scope,
                scope_uid,
                attempt + 1,
                exc,
            )
            await asyncio.sleep(1 + attempt)

    logger.exception(
        "skill_factory_worker 重試耗盡 scope=%s scope_uid=%s err=%s",
        scope,
        scope_uid,
        last_err,
    )
    # 本版不設 DLQ：純失敗只 log，不阻塞其他事件
    _ = time.time()
