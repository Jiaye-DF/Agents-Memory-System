"""記憶 pipeline trace 寫入 / 讀取（v1.3.1）。

每個 session 一條 Redis stream `memory:trace:{session_uid}`，
worker 每階段 XADD 一筆，TTL 7 天，MAXLEN ~ 200。

設計重點：
- record() 失敗一律僅 log warning，不 raise（不阻塞 worker 主流程）
- read() 由 admin endpoint 呼叫，回 list[dict]，由上層轉 schema
- 不新增 DB 表；trace 為 ephemeral 觀察資料
"""

from __future__ import annotations

import json
import logging
import time

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


# ---------- 常數 ----------

TRACE_KEY_FMT = "memory:trace:{session_uid}"
TRACE_MAX_LEN = 200
TRACE_TTL_SECONDS = 7 * 86400


def _trace_key(session_uid: str) -> str:
    return TRACE_KEY_FMT.format(session_uid=session_uid)


# ---------- 寫入 ----------


async def record(
    session_uid: str,
    step: str,
    *,
    outcome: str = "ok",
    duration_ms: int | None = None,
    message_uids: list[str] | None = None,
    extra: dict[str, object] | None = None,
) -> None:
    """寫入一筆 trace。失敗僅 log warning，不影響主流程。"""
    if not session_uid or not step:
        return
    payload: dict[str, str] = {
        "step": step,
        "outcome": outcome,
        "ts": str(int(time.time() * 1000)),
        "message_uids": json.dumps(
            [str(u) for u in (message_uids or [])], ensure_ascii=False
        ),
        "extra": json.dumps(extra or {}, ensure_ascii=False, default=str),
    }
    if duration_ms is not None:
        payload["duration_ms"] = str(int(duration_ms))

    try:
        redis = get_redis()
    except RuntimeError:
        logger.debug("memory_trace: Redis 尚未初始化，略過 record session=%s", session_uid)
        return

    key = _trace_key(session_uid)
    try:
        await redis.xadd(
            key,
            payload,
            maxlen=TRACE_MAX_LEN,
            approximate=True,
        )
        # 每次 XADD 後刷新 TTL，避免 stream 在沉寂後過早消失
        await redis.expire(key, TRACE_TTL_SECONDS)
    except Exception as exc:
        logger.warning(
            "memory_trace: 寫入失敗 session=%s step=%s: %s",
            session_uid,
            step,
            exc,
        )


# ---------- 讀取 ----------


async def read(session_uid: str, limit: int = 200) -> list[dict[str, object]]:
    """讀取 session trace；找不到回空 list。

    回傳結構：每筆 dict 含
      - ts: int (unix ms)
      - step: str
      - outcome: str
      - duration_ms: int | None
      - message_uids: list[str]
      - extra: dict
    """
    try:
        redis = get_redis()
    except RuntimeError:
        return []

    key = _trace_key(session_uid)
    try:
        entries = await redis.xrange(key, count=limit)
    except Exception as exc:
        logger.warning(
            "memory_trace: 讀取失敗 session=%s: %s", session_uid, exc
        )
        return []

    items: list[dict[str, object]] = []
    for entry_id, fields in entries:
        if not isinstance(fields, dict):
            continue
        try:
            ts = int(fields.get("ts") or 0)
        except (TypeError, ValueError):
            ts = 0
        try:
            duration_ms_raw = fields.get("duration_ms")
            duration_ms = (
                int(duration_ms_raw) if duration_ms_raw not in (None, "") else None
            )
        except (TypeError, ValueError):
            duration_ms = None
        try:
            message_uids_raw = fields.get("message_uids") or "[]"
            message_uids = json.loads(message_uids_raw)
            if not isinstance(message_uids, list):
                message_uids = []
        except Exception:
            message_uids = []
        try:
            extra_raw = fields.get("extra") or "{}"
            extra = json.loads(extra_raw)
            if not isinstance(extra, dict):
                extra = {}
        except Exception:
            extra = {}

        items.append(
            {
                "entry_id": str(entry_id),
                "ts": ts,
                "step": fields.get("step") or "",
                "outcome": fields.get("outcome") or "",
                "duration_ms": duration_ms,
                "message_uids": [str(u) for u in message_uids],
                "extra": extra,
            }
        )
    # XRANGE 已是時間升序；保險再以 ts 排序避免 stream id 同毫秒亂序
    items.sort(key=lambda it: (it["ts"], it["entry_id"]))
    return items
