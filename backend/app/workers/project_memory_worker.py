"""project_memory_worker（v1.3.5 Phase 3）。

設計依據：
- propose §3-1：定期從該 project 下所有 session 的 chat_memory 二次聚合
- propose §3-3 / Arch §5-2：project 層生命週期跟隨 project 刪除
- propose §2-1：聚合 LLM 呼叫的 system prompt 顯式要求繁體中文

主迴圈：
    BRPOP project:memory:queue  → { project_uid, owner_user_uid?, trigger_at }
    → 撈該 project 下所有 chat_memory（list_by_project）
    → 依 topic 分群（同主題合併）
    → 每群送 extract_memory（system_prompt = PROJECT_MEMORY_AGGREGATE_SYSTEM_PROMPT）
       走 v1.3.0 metered wrapper（call_kind=memory_aggregate_project）
    → 二次聚合產 embedding → 寫入 project_memory
    → 失敗：重試 3 次 → DLQ
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Any

from app.clients.openrouter.memory_aggregation_prompts import (
    PROJECT_MEMORY_AGGREGATE_SYSTEM_PROMPT,
)
from app.core.database import AsyncSessionLocal
from app.core.queue_keys import (
    PROJECT_MEMORY_DLQ_KEY,
    PROJECT_MEMORY_QUEUE_KEY,
)
from app.core.redis import get_redis
from app.models.chat_memory import ChatMemory
from app.repositories import (
    chat_memory_repository,
    project_memory_repository,
)
from app.services import llm_metering, system_setting_service

logger = logging.getLogger(__name__)

QUEUE_KEY = PROJECT_MEMORY_QUEUE_KEY
DLQ_KEY = PROJECT_MEMORY_DLQ_KEY
BRPOP_TIMEOUT = 5
MAX_RETRY = 3
DEFAULT_AGGREGATION_MODEL = "anthropic/claude-haiku-4-5"
DEFAULT_MIN_CHAT_MEMORY_COUNT = 5
DEFAULT_GROUP_INPUT_MAX_CHARS = 4000


def _log_event(
    step: str,
    project_uid: str | None,
    *,
    outcome: str = "ok",
    duration_ms: int | None = None,
    level: str = "info",
    **extra: Any,
) -> None:
    """v1.3.1 結構化 log 風格（與 memory_worker 對齊）。"""
    payload: dict[str, Any] = {
        "step": step,
        "project_uid": project_uid,
        "outcome": outcome,
        "duration_ms": duration_ms,
    }
    if extra:
        payload.update(extra)
    msg = "project_memory_worker step=%s project=%s outcome=%s duration_ms=%s"
    args = (step, project_uid, outcome, duration_ms)
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
            project_uid = data.get("project_uid") or data.get("chat_project_uid")
            owner_user_uid = data.get("owner_user_uid")
        except Exception as exc:
            _log_event(
                "parse",
                None,
                outcome="error",
                level="warning",
                error=str(exc),
            )
            continue

        if not project_uid:
            _log_event(
                "parse",
                None,
                outcome="missing_project_uid",
                level="warning",
            )
            continue

        await _handle(str(project_uid), owner_user_uid)


async def _handle(project_uid: str, owner_user_uid: str | None) -> None:
    last_err: Exception | None = None
    for attempt in range(MAX_RETRY):
        try:
            async with AsyncSessionLocal() as db:
                await _aggregate_project(project_uid, owner_user_uid, db)
                await db.commit()
            return
        except Exception as exc:
            last_err = exc
            _log_event(
                "aggregate",
                project_uid,
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
                    "project_uid": project_uid,
                    "owner_user_uid": owner_user_uid,
                    "error": str(last_err) if last_err else "unknown",
                    "ts": time.time(),
                }
            ),
        )
        _log_event(
            "dlq",
            project_uid,
            outcome="pushed",
            level="error",
            error=str(last_err) if last_err else "unknown",
        )
    except Exception as exc:
        _log_event(
            "dlq",
            project_uid,
            outcome="push_failed",
            level="error",
            error=str(exc),
        )


async def _aggregate_project(
    project_uid: str,
    owner_user_uid: str | None,
    db: Any,
) -> None:
    """單一 project 的二次聚合主流程。"""
    started = time.time()

    min_count = await system_setting_service.get_int(
        "memory.project.min_chat_memory_count",
        DEFAULT_MIN_CHAT_MEMORY_COUNT,
        db,
    )
    model = await system_setting_service.get(
        "memory.aggregation_extractor_model",
        DEFAULT_AGGREGATION_MODEL,
        db,
    )
    if not model:
        model = DEFAULT_AGGREGATION_MODEL

    chat_memories = await chat_memory_repository.list_by_project(project_uid, db)
    if len(chat_memories) < min_count:
        _log_event(
            "skip_below_threshold",
            project_uid,
            chat_memory_count=len(chat_memories),
            threshold=min_count,
        )
        return

    # 依 topic 分群（None / 空字串歸到 "_untitled"）
    groups = _group_by_topic(chat_memories)
    _log_event(
        "groups_built",
        project_uid,
        total_chat_memories=len(chat_memories),
        groups=len(groups),
    )

    aggregated_count = 0
    for topic_key, group_memories in groups.items():
        try:
            await _aggregate_one_group(
                project_uid=project_uid,
                owner_user_uid=owner_user_uid,
                topic_key=topic_key,
                group_memories=group_memories,
                model=model,
                db=db,
            )
            aggregated_count += 1
        except Exception as exc:
            # per-group try / except：單群失敗不影響其他群
            _log_event(
                "group_aggregate",
                project_uid,
                outcome="failed",
                level="warning",
                topic_key=topic_key,
                error=str(exc),
            )
            continue

    duration_ms = int((time.time() - started) * 1000)
    _log_event(
        "write",
        project_uid,
        duration_ms=duration_ms,
        groups_total=len(groups),
        groups_written=aggregated_count,
    )

    # v1.3.6：聚合完成 → 觸發 Skill 工廠 project scope analyzer
    if aggregated_count > 0 and owner_user_uid:
        try:
            redis = get_redis()
            await redis.lpush(
                "skill_factory_queue",
                json.dumps(
                    {
                        "user_uid": owner_user_uid,
                        "scope": "project",
                        "scope_uid": project_uid,
                    }
                ),
            )
            _log_event(
                "skill_factory_trigger",
                project_uid,
                outcome="ok",
                user_uid=owner_user_uid,
            )
        except Exception as exc:
            _log_event(
                "skill_factory_trigger",
                project_uid,
                outcome="failed",
                level="warning",
                error=str(exc),
            )


def _group_by_topic(memories: list[ChatMemory]) -> dict[str, list[ChatMemory]]:
    """以 topic 字串為 key 分群（None / 空字串歸到 "_untitled"）。

    v0.1 簡化策略：直接字串 equality；衝突合併（mem0 風格）放後續版本。
    """
    groups: dict[str, list[ChatMemory]] = defaultdict(list)
    for m in memories:
        key = (m.topic or "").strip() or "_untitled"
        groups[key].append(m)
    return groups


async def _aggregate_one_group(
    *,
    project_uid: str,
    owner_user_uid: str | None,
    topic_key: str,
    group_memories: list[ChatMemory],
    model: str,
    db: Any,
) -> None:
    """單一主題群的聚合：extract_memory（中文 system prompt）→ embedding → insert。"""
    # 組輸入：每筆 chat_memory 用一行表達 topic / keywords / entities
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

    # ---- extract（二次聚合） ----
    try:
        extract_result = await llm_metering.call_llm_metered(
            purpose=llm_metering.PURPOSE_MEMORY_EXTRACT,
            session_uid=None,
            user_uid=owner_user_uid,
            messages=llm_messages,
            model=model,
            system_prompt=PROJECT_MEMORY_AGGREGATE_SYSTEM_PROMPT,
        )
    except Exception as exc:
        raise RuntimeError(f"project 聚合 extract 失敗: {exc}") from exc

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
            user_uid=owner_user_uid,
            text=embed_input,
        )
    except Exception as exc:
        raise RuntimeError(f"project 聚合 embedding 失敗: {exc}") from exc

    # ---- insert ----
    source_session_uids = list(
        {str(m.chat_session_uid) for m in group_memories}
    )
    source_message_uids: list[str] = []
    for m in group_memories:
        for u in m.source_chat_message_uids or []:
            source_message_uids.append(str(u))
    # 去重保序（不依賴 set 變動順序）
    seen: set[str] = set()
    deduped_msg_uids: list[str] = []
    for u in source_message_uids:
        if u in seen:
            continue
        seen.add(u)
        deduped_msg_uids.append(u)

    created = await project_memory_repository.create(
        {
            "chat_project_uid": project_uid,
            "source_session_uids": source_session_uids,
            "source_chat_message_uids": deduped_msg_uids,
            "keywords": list(extract_result.keywords),
            "entities": list(extract_result.entities),
            "topic": extract_result.topic or topic_key,
            "embedding": vector,
        },
        db,
    )
    _log_event(
        "group_aggregate",
        project_uid,
        topic_key=topic_key,
        memory_uid=str(created.project_memory_uid),
        src_sessions=len(source_session_uids),
        src_chat_memories=len(group_memories),
    )
