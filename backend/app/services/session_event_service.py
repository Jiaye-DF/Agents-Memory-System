"""Session 級別非同步事件 service：
集中管理 Redis pub/sub channel 命名、事件型別常數，以及 publish 入口。

設計重點：
- publish 失敗一律僅 log warning，不 raise（不阻塞主流程，例如 memory_worker）
- 事件型別字串集中於本檔，避免前後端各自硬寫字串而走樣
- v1.3.2 僅實作 `memory_updated` / `memory_failed`；`session_archived` 僅保留常數，
  待後續版本決定觸發來源
"""

import json
import logging
import time

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


# ---------- channel / event 常數 ----------

# Redis pub/sub channel 命名（與既有 list queue `chat:memory:queue` / `chat:memory:dlq` 分流）
MEMORY_CHANNEL_FMT = "chat:session:{session_uid}:memory"

EVENT_MEMORY_UPDATED = "memory_updated"
EVENT_MEMORY_FAILED = "memory_failed"
# 預留欄位定義；v1.3.2 不實作觸發
EVENT_SESSION_ARCHIVED = "session_archived"
# SSE handler 開場用，讓前端能確認連線建立並停掉 polling fallback
EVENT_READY = "ready"


def channel_for_session(session_uid: str) -> str:
    return MEMORY_CHANNEL_FMT.format(session_uid=session_uid)


# ---------- publish helpers ----------

async def publish_memory_updated(session_uid: str, memory_uid: str) -> None:
    """memory_worker 寫入 chat_memory 後呼叫；失敗僅 log warning。"""
    payload = {
        "event": EVENT_MEMORY_UPDATED,
        "memory_uid": memory_uid,
        "ts": int(time.time()),
    }
    await _publish(session_uid, payload)


async def publish_memory_failed(
    session_uid: str, message_uids: list[str], error: str
) -> None:
    """memory_worker 重試耗盡進入 DLQ 時呼叫；失敗僅 log warning。"""
    payload = {
        "event": EVENT_MEMORY_FAILED,
        "message_uids": [str(u) for u in message_uids],
        "error": error,
        "ts": int(time.time()),
    }
    await _publish(session_uid, payload)


async def _publish(session_uid: str, payload: dict) -> None:
    try:
        redis = get_redis()
        await redis.publish(channel_for_session(session_uid), json.dumps(payload))
    except Exception as exc:
        logger.warning(
            "session_event publish 失敗 session=%s event=%s: %s",
            session_uid,
            payload.get("event"),
            exc,
        )
