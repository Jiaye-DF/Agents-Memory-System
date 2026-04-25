"""user_memory_worker（v1.3.5 Phase 4）。

設計依據：
- propose §3-1：跨 project 的長期偏好聚合（語言 / 風格 / 領域 / 慣用工具等）
- propose §5-2 升級 A：user_memory 給 Skill 工廠正式版做 cross-session pattern 偵測
- propose §2-1：聚合 LLM system prompt 顯式要求繁體中文

主迴圈：
    BRPOP user:memory:queue → { user_uid, trigger_at }
    → 撈該 user 30 天時間窗內的 chat_memory（list_by_user）
    → 觸發條件（同時成立才聚合）：
        - 同主題 ≥ N 筆（N 預設 5）
        - 同主題占比 ≥ M%（M 預設 60）
    → 達標主題群 → extract_memory（USER_MEMORY_AGGREGATE_SYSTEM_PROMPT）
       → embedding → 寫入 user_memory
    → 失敗：MAX_RETRY=3 → DLQ
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.clients.openrouter.memory_aggregation_prompts import (
    USER_MEMORY_AGGREGATE_SYSTEM_PROMPT,
)
from app.core.database import AsyncSessionLocal
from app.core.queue_keys import USER_MEMORY_DLQ_KEY, USER_MEMORY_QUEUE_KEY
from app.core.redis import get_redis
from app.models.chat_memory import ChatMemory
from app.repositories import (
    chat_memory_repository,
    chat_session_repository,
    user_memory_repository,
)
from app.services import llm_metering, system_setting_service

logger = logging.getLogger(__name__)

QUEUE_KEY = USER_MEMORY_QUEUE_KEY
DLQ_KEY = USER_MEMORY_DLQ_KEY
BRPOP_TIMEOUT = 5
MAX_RETRY = 3
DEFAULT_AGGREGATION_MODEL = "anthropic/claude-haiku-4-5"
DEFAULT_MIN_SESSION_COUNT = 5
DEFAULT_TOPIC_CONCENTRATION_PCT = 60
DEFAULT_TIME_WINDOW_DAYS = 30
DEFAULT_GROUP_INPUT_MAX_CHARS = 4000


def _log_event(
    step: str,
    user_uid: str | None,
    *,
    outcome: str = "ok",
    duration_ms: int | None = None,
    level: str = "info",
    **extra: Any,
) -> None:
    payload: dict[str, Any] = {
        "step": step,
        "user_uid": user_uid,
        "outcome": outcome,
        "duration_ms": duration_ms,
    }
    if extra:
        payload.update(extra)
    msg = "user_memory_worker step=%s user=%s outcome=%s duration_ms=%s"
    args = (step, user_uid, outcome, duration_ms)
    fn = {
        "info": logger.info,
        "warning": logger.warning,
        "error": logger.error,
    }.get(level, logger.info)
    fn(msg, *args, extra={"event": payload})


async def run() -> None:
    _log_event("boot", None)

    while True:
        try:
            redis = get_redis()
        except RuntimeError:
            await asyncio.sleep(1)
            continue

        try:
            item = await redis.brpop(QUEUE_KEY, timeout=BRPOP_TIMEOUT)
        except asyncio.CancelledError:
            _log_event("boot", None, outcome="cancelled")
            raise
        except Exception as exc:
            _log_event(
                "brpop",
                None,
                outcome="error",
                level="warning",
                error=str(exc),
            )
            await asyncio.sleep(2)
            continue

        if item is None:
            continue

        try:
            _, raw = item
            data = json.loads(raw)
            user_uid = data.get("user_uid") or data.get("owner_user_uid")
        except Exception as exc:
            _log_event(
                "parse",
                None,
                outcome="error",
                level="warning",
                error=str(exc),
            )
            continue

        if not user_uid:
            _log_event(
                "parse",
                None,
                outcome="missing_user_uid",
                level="warning",
            )
            continue

        await _handle(str(user_uid))


async def _handle(user_uid: str) -> None:
    last_err: Exception | None = None
    for attempt in range(MAX_RETRY):
        try:
            async with AsyncSessionLocal() as db:
                await _aggregate_user(user_uid, db)
                await db.commit()
            return
        except Exception as exc:
            last_err = exc
            _log_event(
                "aggregate",
                user_uid,
                outcome="retry",
                level="warning",
                attempt=attempt + 1,
                error=str(exc),
            )
            await asyncio.sleep(1 + attempt)

    # 重試耗盡 → DLQ
    try:
        redis = get_redis()
        await redis.lpush(
            DLQ_KEY,
            json.dumps(
                {
                    "user_uid": user_uid,
                    "error": str(last_err) if last_err else "unknown",
                    "ts": time.time(),
                }
            ),
        )
        _log_event(
            "dlq",
            user_uid,
            outcome="pushed",
            level="error",
            error=str(last_err) if last_err else "unknown",
        )
    except Exception as exc:
        _log_event(
            "dlq",
            user_uid,
            outcome="push_failed",
            level="error",
            error=str(exc),
        )


async def _aggregate_user(user_uid: str, db: Any) -> None:
    started = time.time()

    min_session_count = await system_setting_service.get_int(
        "memory.user.min_session_count", DEFAULT_MIN_SESSION_COUNT, db
    )
    concentration_pct = await system_setting_service.get_int(
        "memory.user.topic_concentration_pct",
        DEFAULT_TOPIC_CONCENTRATION_PCT,
        db,
    )
    model = await system_setting_service.get(
        "memory.aggregation_extractor_model",
        DEFAULT_AGGREGATION_MODEL,
        db,
    )
    if not model:
        model = DEFAULT_AGGREGATION_MODEL

    since = datetime.now(timezone.utc) - timedelta(days=DEFAULT_TIME_WINDOW_DAYS)
    chat_memories = await chat_memory_repository.list_by_user(
        user_uid, db, since=since
    )
    total = len(chat_memories)
    if total == 0:
        _log_event(
            "skip_no_data",
            user_uid,
            window_days=DEFAULT_TIME_WINDOW_DAYS,
        )
        return

    # 依 topic 分群，計算每群筆數與占比
    groups = _group_by_topic(chat_memories)
    qualified: list[tuple[str, list[ChatMemory], float]] = []
    for topic_key, members in groups.items():
        count = len(members)
        pct = (count / total) * 100.0
        if count >= min_session_count and pct >= concentration_pct:
            qualified.append((topic_key, members, pct))

    _log_event(
        "groups_built",
        user_uid,
        total_chat_memories=total,
        groups=len(groups),
        qualified=len(qualified),
        min_session_count=min_session_count,
        concentration_pct=concentration_pct,
    )
    if not qualified:
        return

    aggregated_count = 0
    for topic_key, members, pct in qualified:
        try:
            await _aggregate_one_group(
                user_uid=user_uid,
                topic_key=topic_key,
                group_memories=members,
                pct=pct,
                model=model,
                db=db,
            )
            aggregated_count += 1
        except Exception as exc:
            _log_event(
                "group_aggregate",
                user_uid,
                outcome="failed",
                level="warning",
                topic_key=topic_key,
                error=str(exc),
            )
            continue

    duration_ms = int((time.time() - started) * 1000)
    _log_event(
        "write",
        user_uid,
        duration_ms=duration_ms,
        groups_qualified=len(qualified),
        groups_written=aggregated_count,
    )

    # v1.3.6：聚合完成 → 觸發 Skill 工廠 user scope analyzer
    if aggregated_count > 0:
        try:
            redis = get_redis()
            await redis.lpush(
                "skill_factory_queue",
                json.dumps(
                    {
                        "user_uid": user_uid,
                        "scope": "user",
                        "scope_uid": user_uid,
                    }
                ),
            )
            _log_event(
                "skill_factory_trigger",
                user_uid,
                outcome="ok",
            )
        except Exception as exc:
            _log_event(
                "skill_factory_trigger",
                user_uid,
                outcome="failed",
                level="warning",
                error=str(exc),
            )


def _group_by_topic(memories: list[ChatMemory]) -> dict[str, list[ChatMemory]]:
    groups: dict[str, list[ChatMemory]] = defaultdict(list)
    for m in memories:
        key = (m.topic or "").strip() or "_untitled"
        groups[key].append(m)
    return groups


async def _aggregate_one_group(
    *,
    user_uid: str,
    topic_key: str,
    group_memories: list[ChatMemory],
    pct: float,
    model: str,
    db: Any,
) -> None:
    """單一達標主題群的長期偏好聚合。"""
    lines: list[str] = []
    for m in group_memories:
        kw = ", ".join(list(m.keywords or []))
        en = ", ".join(list(m.entities or []))
        lines.append(
            f"[{m.topic or '_untitled'}] keywords: {kw} | entities: {en}"
        )
    combined = "\n".join(lines)
    if len(combined) > DEFAULT_GROUP_INPUT_MAX_CHARS:
        combined = combined[:DEFAULT_GROUP_INPUT_MAX_CHARS]

    llm_messages = [{"role": "user", "content": combined}]

    # ---- extract（長期偏好抽取） ----
    try:
        extract_result = await llm_metering.call_llm_metered(
            purpose=llm_metering.PURPOSE_MEMORY_EXTRACT,
            session_uid=None,
            user_uid=user_uid,
            messages=llm_messages,
            model=model,
            system_prompt=USER_MEMORY_AGGREGATE_SYSTEM_PROMPT,
        )
    except Exception as exc:
        raise RuntimeError(f"user 聚合 extract 失敗: {exc}") from exc

    # ---- embedding ----
    embed_input = "，".join(
        list(extract_result.keywords)
        + list(extract_result.entities)
        + ([extract_result.topic] if extract_result.topic else [])
    )
    if not embed_input.strip():
        embed_input = combined[:1000]
    try:
        vector = await llm_metering.call_llm_metered(
            purpose=llm_metering.PURPOSE_EMBEDDING,
            session_uid=None,
            user_uid=user_uid,
            text=embed_input,
        )
    except Exception as exc:
        raise RuntimeError(f"user 聚合 embedding 失敗: {exc}") from exc

    # ---- 整理來源（session / project） ----
    source_session_uids = list(
        {str(m.chat_session_uid) for m in group_memories}
    )
    # 來源 project：JOIN session 取 chat_project_uid（容忍游離 session 為 None）
    source_project_uids: list[str] = []
    project_seen: set[str] = set()
    for sid in source_session_uids:
        try:
            sess = await chat_session_repository.get_by_uid(sid, db)
        except Exception:
            sess = None
        if sess is not None and sess.chat_project_uid is not None:
            puid = str(sess.chat_project_uid)
            if puid not in project_seen:
                project_seen.add(puid)
                source_project_uids.append(puid)

    created = await user_memory_repository.create(
        {
            "owner_user_uid": user_uid,
            "source_session_uids": source_session_uids,
            "source_project_uids": source_project_uids,
            "keywords": list(extract_result.keywords),
            "entities": list(extract_result.entities),
            "topic": extract_result.topic or topic_key,
            "embedding": vector,
        },
        db,
    )
    _log_event(
        "group_aggregate",
        user_uid,
        topic_key=topic_key,
        memory_uid=str(created.user_memory_uid),
        src_sessions=len(source_session_uids),
        src_projects=len(source_project_uids),
        src_chat_memories=len(group_memories),
        topic_pct=round(pct, 2),
    )
