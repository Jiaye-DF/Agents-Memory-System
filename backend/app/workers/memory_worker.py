import asyncio
import base64
import json
import logging
import time

from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.queue_keys import (
    MEMORY_DLQ_KEY,
    MEMORY_QUEUE_KEY,
    PROJECT_MEMORY_QUEUE_KEY,
    USER_MEMORY_QUEUE_KEY,
)
from app.core.redis import get_blocking_redis, get_redis
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.repositories import (
    chat_attachment_repository,
    chat_memory_repository,
    chat_message_repository,
)
from app.services import (
    llm_metering,
    memory_prefilter,
    memory_trace_service,
    session_event_service,
    system_setting_service,
)
from app.storage import s3_storage

logger = logging.getLogger(__name__)

# v1.3.1：常數抽至 app.core.queue_keys，但保留別名以維持既有引用
QUEUE_KEY = MEMORY_QUEUE_KEY
DLQ_KEY = MEMORY_DLQ_KEY
BRPOP_TIMEOUT = 5
MAX_RETRY = 3
DEFAULT_EXTRACTOR_MODEL = "anthropic/claude-haiku-4-5"
DEFAULT_IMAGE_DESCRIBE_MODEL = "anthropic/claude-haiku-4-5"
DEFAULT_BATCH_SIZE = 5
DEFAULT_IDLE_SECONDS = 60
DEFAULT_SKIP_RULES: dict = {
    "min_length": 15,
    "greeting_whitelist": ["hi", "hello", "好", "好的", "收到", "謝謝", "ok"],
    "max_tokens": 2000,
}


# ---------- v1.3.1：結構化 log helper ----------

def _log_event(
    step: str,
    session_uid: str | None,
    *,
    message_uids: list[str] | None = None,
    outcome: str = "ok",
    duration_ms: int | None = None,
    level: str = "info",
    **extra: object,
) -> None:
    """統一輸出結構化 log（沿用標準 logging，extra 帶 dict）。

    訊息採 lazy formatting，避免 logging f-string；結構化欄位放 extra 供
    後續 log shipping 解析。
    """
    payload: dict[str, object] = {
        "step": step,
        "session_uid": session_uid,
        "outcome": outcome,
        "duration_ms": duration_ms,
        "message_uids": message_uids,
    }
    if extra:
        payload.update(extra)

    msg = "memory_worker step=%s session=%s outcome=%s duration_ms=%s"
    args = (step, session_uid, outcome, duration_ms)
    fn = {
        "info": logger.info,
        "warning": logger.warning,
        "error": logger.error,
    }.get(level, logger.info)
    fn(msg, *args, extra={"event": payload})


async def run() -> None:
    """Memory Worker 主迴圈：消費 Redis 佇列 → 批次抽取 → embedding → 寫入 chat_memory。"""
    _log_event("boot", None)
    buffer: dict[str, list[str]] = {}
    last_seen: dict[str, float] = {}

    while True:
        try:
            redis = get_blocking_redis()
        except RuntimeError:
            await asyncio.sleep(1)
            continue

        try:
            item = await redis.brpop(QUEUE_KEY, timeout=BRPOP_TIMEOUT)
        except asyncio.CancelledError:
            _log_event("boot", None, outcome="cancelled")
            raise
        except RedisTimeoutError:
            # socket timeout < BRPOP_TIMEOUT 時佇列閒置即逾時，屬 idle 而非錯誤
            continue
        except Exception as exc:
            _log_event(
                "enqueue",
                None,
                outcome="brpop_error",
                level="warning",
                error=str(exc),
            )
            await asyncio.sleep(2)
            continue

        if item is not None:
            try:
                _, raw = item
                data = json.loads(raw)
                sid = data.get("session_uid")
                mid = data.get("message_uid")
                if sid and mid:
                    buffer.setdefault(sid, []).append(mid)
                    last_seen[sid] = time.time()
                    _log_event(
                        "enqueue",
                        sid,
                        message_uids=[str(mid)],
                        buffered=len(buffer[sid]),
                    )
                    await memory_trace_service.record(
                        sid,
                        "enqueue",
                        message_uids=[str(mid)],
                        extra={"buffered": len(buffer[sid])},
                    )
            except Exception as exc:
                _log_event(
                    "enqueue",
                    None,
                    outcome="parse_error",
                    level="warning",
                    error=str(exc),
                )

        # 檢查 buffer 是否達批次條件
        if not buffer:
            continue

        try:
            async with AsyncSessionLocal() as cfg_db:
                batch_size = await system_setting_service.get_int(
                    "memory.batch_size", DEFAULT_BATCH_SIZE, cfg_db
                )
                idle_s = await system_setting_service.get_int(
                    "memory.idle_seconds", DEFAULT_IDLE_SECONDS, cfg_db
                )
        except Exception as exc:
            _log_event(
                "config",
                None,
                outcome="load_failed",
                level="warning",
                error=str(exc),
            )
            batch_size = DEFAULT_BATCH_SIZE
            idle_s = DEFAULT_IDLE_SECONDS

        now = time.time()
        for sid in list(buffer.keys()):
            mids = buffer.get(sid, [])
            if not mids:
                continue
            is_full = len(mids) >= batch_size
            is_idle = now - last_seen.get(sid, now) >= idle_s
            if not (is_full or is_idle):
                continue
            reason = "full" if is_full else "idle"
            mids_snapshot = [str(m) for m in mids]
            _log_event(
                "buffer_flush",
                sid,
                message_uids=mids_snapshot,
                reason=reason,
            )
            await memory_trace_service.record(
                sid,
                "buffer_flush",
                message_uids=mids_snapshot,
                extra={"reason": reason, "batch_size": len(mids_snapshot)},
            )
            try:
                async with AsyncSessionLocal() as db:
                    await _process_batch(sid, list(mids), db)
                    await db.commit()
            except Exception as exc:
                _log_event(
                    "buffer_flush",
                    sid,
                    message_uids=mids_snapshot,
                    outcome="exception",
                    level="warning",
                    error=str(exc),
                )
                logger.exception(
                    "memory_worker 處理批次失敗 session=%s: %s", sid, exc
                )
                await memory_trace_service.record(
                    sid,
                    "buffer_flush",
                    outcome="exception",
                    message_uids=mids_snapshot,
                    extra={"error": str(exc)},
                )
            buffer.pop(sid, None)
            last_seen.pop(sid, None)


async def _describe_image_attachments(
    message: ChatMessage,
    model: str,
    db: AsyncSession,
    *,
    session_uid: str,
    user_uid: str | None,
) -> str:
    """
    對訊息帶的圖片附件各產一句中文描述；
    單張失敗不影響其他張，整體失敗時回空字串（由呼叫端 fallback）。
    """
    raw_uids = message.attachment_uids
    if not raw_uids:
        return ""
    uids = [str(u) for u in raw_uids]

    try:
        attachments = await chat_attachment_repository.list_by_uids(uids, db)
    except Exception as exc:
        _log_event(
            "image_describe",
            session_uid,
            message_uids=[str(message.chat_message_uid)],
            outcome="load_attachment_failed",
            level="warning",
            error=str(exc),
        )
        return ""

    descriptions: list[str] = []
    described_count = 0
    started = time.time()
    for a in attachments:
        mime = (a.file_type or "").lower()
        if not mime.startswith("image/"):
            continue
        try:
            raw = await s3_storage.get_object(a.storage_key)
            b64 = base64.b64encode(raw).decode("ascii")
            data_url = f"data:{mime};base64,{b64}"
            # v1.3.0：經 llm_metering 集中進入點記成本 / 延遲
            desc = await llm_metering.call_llm_metered(
                purpose=llm_metering.PURPOSE_IMAGE_DESCRIBE,
                session_uid=session_uid,
                user_uid=user_uid,
                image_data_url=data_url,
                model=model,
            )
            if desc:
                descriptions.append(f"{a.file_name}：{desc}")
                described_count += 1
        except Exception as exc:
            _log_event(
                "image_describe",
                session_uid,
                outcome="single_failed",
                level="warning",
                attachment_uid=str(a.chat_attachment_uid),
                error=str(exc),
            )
            continue

    if described_count > 0:
        duration_ms = int((time.time() - started) * 1000)
        _log_event(
            "image_describe",
            session_uid,
            message_uids=[str(message.chat_message_uid)],
            duration_ms=duration_ms,
            count=described_count,
        )
        await memory_trace_service.record(
            session_uid,
            "image_describe",
            duration_ms=duration_ms,
            message_uids=[str(message.chat_message_uid)],
            extra={"count": described_count},
        )
    return " / ".join(descriptions)


async def _process_batch(
    session_uid: str, message_uids: list[str], db: AsyncSession
) -> None:
    # 讀設定
    rules = await system_setting_service.get_json(
        "memory.skip_rules", DEFAULT_SKIP_RULES, db
    )
    if not isinstance(rules, dict):
        rules = DEFAULT_SKIP_RULES
    max_tokens = int(rules.get("max_tokens", 2000) or 2000)
    model = await system_setting_service.get(
        "memory.extractor_model", DEFAULT_EXTRACTOR_MODEL, db
    )
    if not model:
        model = DEFAULT_EXTRACTOR_MODEL
    image_describe_model = await system_setting_service.get(
        "memory.image_describe_model", DEFAULT_IMAGE_DESCRIBE_MODEL, db
    )
    if not image_describe_model:
        image_describe_model = DEFAULT_IMAGE_DESCRIBE_MODEL

    # v1.3.0：metering 用 — 透傳 user_uid 到 LLM 呼叫
    from app.repositories import chat_session_repository as _csr

    session_obj = await _csr.get_by_uid(session_uid, db)
    owner_user_uid: str | None = (
        str(session_obj.owner_user_uid) if session_obj else None
    )

    # 讀訊息
    messages: list[ChatMessage] = []
    for mid in message_uids:
        m = await chat_message_repository.get_by_uid(mid, db)
        if m is not None:
            messages.append(m)
    if not messages:
        return

    total = len(messages)
    kept = [m for m in messages if not memory_prefilter.should_skip(m, rules)]
    skipped = total - len(kept)
    kept_uids = [str(m.chat_message_uid) for m in kept]
    _log_event(
        "prefilter",
        session_uid,
        message_uids=kept_uids,
        total=total,
        kept=len(kept),
        skipped=skipped,
    )
    await memory_trace_service.record(
        session_uid,
        "prefilter",
        message_uids=kept_uids,
        extra={"total": total, "kept": len(kept), "skipped": skipped},
    )
    if not kept:
        _log_event(
            "prefilter",
            session_uid,
            outcome="all_skipped",
            total=total,
        )
        await memory_trace_service.record(
            session_uid,
            "prefilter",
            outcome="all_skipped",
            extra={"total": total},
        )
        return

    # 組送給小模型的 messages；若 user 訊息帶圖片附件，先用 vision model 產描述
    # 文字檔 / PDF 的 filename 標記已由 chat_service 拼入訊息 content，此處不再重複處理
    combined_lines: list[str] = []
    for m in kept:
        text = memory_prefilter.truncate_for_extraction(m.content, max_tokens)
        image_desc = await _describe_image_attachments(
            m,
            image_describe_model,
            db,
            session_uid=session_uid,
            user_uid=owner_user_uid,
        )
        merged = text
        if image_desc:
            merged = f"{text}\n[圖片描述] {image_desc}" if text else image_desc
        combined_lines.append(f"[{m.role}] {merged}")
    combined = "\n".join(combined_lines)
    combined = memory_prefilter.truncate_for_extraction(combined, max_tokens)

    llm_messages = [{"role": "user", "content": combined}]

    # 抽取 + embedding（合併重試）
    last_err: Exception | None = None
    for attempt in range(MAX_RETRY):
        try:
            # ---- extract ----
            extract_started = time.time()
            try:
                # v1.3.0：經 llm_metering 集中進入點
                extract_result = await llm_metering.call_llm_metered(
                    purpose=llm_metering.PURPOSE_MEMORY_EXTRACT,
                    session_uid=session_uid,
                    user_uid=owner_user_uid,
                    messages=llm_messages,
                    model=model,
                )
            except Exception:
                duration_ms = int((time.time() - extract_started) * 1000)
                _log_event(
                    "extract",
                    session_uid,
                    message_uids=kept_uids,
                    outcome="retry",
                    duration_ms=duration_ms,
                    level="warning",
                    attempt=attempt + 1,
                )
                await memory_trace_service.record(
                    session_uid,
                    "extract",
                    outcome="retry",
                    duration_ms=duration_ms,
                    message_uids=kept_uids,
                    extra={"attempt": attempt + 1},
                )
                raise
            extract_duration = int((time.time() - extract_started) * 1000)
            _log_event(
                "extract",
                session_uid,
                message_uids=kept_uids,
                duration_ms=extract_duration,
                attempt=attempt + 1,
            )
            await memory_trace_service.record(
                session_uid,
                "extract",
                duration_ms=extract_duration,
                message_uids=kept_uids,
                extra={"attempt": attempt + 1},
            )

            # ---- embedding ----
            embed_input = "，".join(
                list(extract_result.keywords)
                + list(extract_result.entities)
                + ([extract_result.topic] if extract_result.topic else [])
            )
            if not embed_input.strip():
                embed_input = combined[:1000]
            embed_started = time.time()
            try:
                vector = await llm_metering.call_llm_metered(
                    purpose=llm_metering.PURPOSE_EMBEDDING,
                    session_uid=session_uid,
                    user_uid=owner_user_uid,
                    text=embed_input,
                )
            except Exception:
                duration_ms = int((time.time() - embed_started) * 1000)
                _log_event(
                    "embedding",
                    session_uid,
                    message_uids=kept_uids,
                    outcome="retry",
                    duration_ms=duration_ms,
                    level="warning",
                    attempt=attempt + 1,
                )
                await memory_trace_service.record(
                    session_uid,
                    "embedding",
                    outcome="retry",
                    duration_ms=duration_ms,
                    message_uids=kept_uids,
                    extra={"attempt": attempt + 1},
                )
                raise
            embed_duration = int((time.time() - embed_started) * 1000)
            _log_event(
                "embedding",
                session_uid,
                message_uids=kept_uids,
                duration_ms=embed_duration,
                attempt=attempt + 1,
            )
            await memory_trace_service.record(
                session_uid,
                "embedding",
                duration_ms=embed_duration,
                message_uids=kept_uids,
                extra={"attempt": attempt + 1},
            )

            created = await chat_memory_repository.create(
                {
                    "chat_session_uid": session_uid,
                    "source_chat_message_uids": [m.chat_message_uid for m in kept],
                    "keywords": list(extract_result.keywords),
                    "entities": list(extract_result.entities),
                    "topic": extract_result.topic or None,
                    "embedding": vector,
                },
                db,
            )
            logger.info(
                "memory_worker 寫入記憶 session=%s, src=%s",
                session_uid,
                len(kept),
            )
            _log_event(
                "write",
                session_uid,
                message_uids=kept_uids,
                src_count=len(kept),
                memory_uid=str(created.chat_memory_uid),
            )
            await memory_trace_service.record(
                session_uid,
                "write",
                message_uids=kept_uids,
                extra={
                    "src_count": len(kept),
                    "memory_uid": str(created.chat_memory_uid),
                },
            )
            # v1.3.2：commit 前 publish memory_updated；失敗僅 warning，不影響主流程
            await session_event_service.publish_memory_updated(
                session_uid, str(created.chat_memory_uid)
            )
            # v1.1.7：觸發 Skill 工廠（不阻塞；由 skill_factory_worker 獨立消費）
            # v1.3.6：payload 加 scope='session'（向後相容：worker 缺 scope 時也視為 session）
            try:
                if owner_user_uid:
                    redis = get_redis()
                    await redis.lpush(
                        "skill_factory_queue",
                        json.dumps(
                            {
                                "user_uid": owner_user_uid,
                                "scope": "session",
                                "scope_uid": session_uid,
                                "session_uid": session_uid,  # 過渡期保留兼容欄位
                            }
                        ),
                    )
            except Exception as exc:
                logger.warning(
                    "memory_worker 推入 skill_factory_queue 失敗 session=%s: %s",
                    session_uid,
                    exc,
                )
            # v1.3.5：條件式觸發 project / user 二次聚合
            #   project：session 屬某 project + 距上次觸發 ≥ idle_hours
            #   user：每寫一筆 chat_memory + 距上次觸發 ≥ idle_hours
            try:
                await _maybe_enqueue_aggregations(
                    session_obj=session_obj,
                    owner_user_uid=owner_user_uid,
                    db=db,
                )
            except Exception as exc:
                logger.warning(
                    "memory_worker 觸發跨層聚合失敗（不影響主流程） session=%s: %s",
                    session_uid,
                    exc,
                )
            return
        except Exception as exc:
            last_err = exc
            # 階段層級的 retry log 已於 extract / embedding 內部寫入；此處保留總覽
            logger.warning(
                "memory_worker 處理失敗 session=%s attempt=%s: %s",
                session_uid,
                attempt + 1,
                exc,
            )
            await asyncio.sleep(1 + attempt)

    # 超過重試上限 → DLQ
    try:
        redis = get_redis()
        await redis.lpush(
            DLQ_KEY,
            json.dumps(
                {
                    "session_uid": session_uid,
                    "message_uids": message_uids,
                    "error": str(last_err) if last_err else "unknown",
                    "ts": time.time(),
                }
            ),
        )
        _log_event(
            "dlq",
            session_uid,
            message_uids=[str(u) for u in message_uids],
            outcome="pushed",
            level="error",
            error=str(last_err) if last_err else "unknown",
        )
        await memory_trace_service.record(
            session_uid,
            "dlq",
            outcome="pushed",
            message_uids=[str(u) for u in message_uids],
            extra={"error": str(last_err) if last_err else "unknown"},
        )
    except Exception as exc:
        _log_event(
            "dlq",
            session_uid,
            outcome="push_failed",
            level="error",
            error=str(exc),
        )
        logger.exception("memory_worker 推入 DLQ 失敗: %s", exc)
        await memory_trace_service.record(
            session_uid,
            "dlq",
            outcome="push_failed",
            extra={"error": str(exc)},
        )

    # v1.3.2：DLQ 進入時亦 publish memory_failed（前端本版不顯示 UI badge，僅記事件）
    await session_event_service.publish_memory_failed(
        session_uid,
        [str(u) for u in message_uids],
        str(last_err) if last_err else "unknown",
    )


# ---------- v1.3.5：跨層聚合觸發（idle 閾值控制） ----------

# 記住上次觸發時間：Redis key（每個 project / user 各一）
_PROJECT_LAST_TRIGGER_KEY = "project:memory:last_trigger:{}"
_USER_LAST_TRIGGER_KEY = "user:memory:last_trigger:{}"
_DEFAULT_PROJECT_IDLE_HOURS = 6
_DEFAULT_USER_IDLE_HOURS = 24


async def _maybe_enqueue_aggregations(
    *,
    session_obj: ChatSession | None,
    owner_user_uid: str | None,
    db: AsyncSession,
) -> None:
    """寫完 chat_memory 後判斷是否觸發 project / user 聚合。

    觸發條件：距上次觸發 ≥ idle_hours（從 Redis key 讀），達標才 LPUSH 訊號。
    無 project（游離 session）時跳過 project 觸發；user 觸發只要有 owner 即可。
    """
    try:
        redis = get_redis()
    except RuntimeError:
        return

    now_ts = time.time()

    # ---- project 層 ----
    project_uid: str | None = None
    if session_obj is not None and session_obj.chat_project_uid is not None:
        project_uid = str(session_obj.chat_project_uid)

    if project_uid:
        try:
            project_idle_hours = await system_setting_service.get_int(
                "memory.project.aggregate_idle_hours",
                _DEFAULT_PROJECT_IDLE_HOURS,
                db,
            )
        except Exception:
            project_idle_hours = _DEFAULT_PROJECT_IDLE_HOURS
        idle_seconds = max(1, project_idle_hours) * 3600

        last_key = _PROJECT_LAST_TRIGGER_KEY.format(project_uid)
        try:
            last_raw = await redis.get(last_key)
            last_ts = float(last_raw) if last_raw else 0.0
        except Exception:
            last_ts = 0.0

        if now_ts - last_ts >= idle_seconds:
            try:
                await redis.lpush(
                    PROJECT_MEMORY_QUEUE_KEY,
                    json.dumps(
                        {
                            "project_uid": project_uid,
                            "owner_user_uid": owner_user_uid,
                            "trigger_at": now_ts,
                        }
                    ),
                )
                # idle 計時用 SETEX，TTL 取 idle 的兩倍避免過早遺忘
                await redis.set(
                    last_key,
                    str(now_ts),
                    ex=idle_seconds * 2,
                )
                logger.info(
                    "memory_worker 觸發 project 聚合 project=%s",
                    project_uid,
                )
            except Exception as exc:
                logger.warning(
                    "memory_worker 推入 project_memory_queue 失敗 project=%s: %s",
                    project_uid,
                    exc,
                )

    # ---- user 層 ----
    if owner_user_uid:
        try:
            user_idle_hours = await system_setting_service.get_int(
                "memory.user.aggregate_idle_hours",
                _DEFAULT_USER_IDLE_HOURS,
                db,
            )
        except Exception:
            user_idle_hours = _DEFAULT_USER_IDLE_HOURS
        idle_seconds = max(1, user_idle_hours) * 3600

        last_key = _USER_LAST_TRIGGER_KEY.format(owner_user_uid)
        try:
            last_raw = await redis.get(last_key)
            last_ts = float(last_raw) if last_raw else 0.0
        except Exception:
            last_ts = 0.0

        if now_ts - last_ts >= idle_seconds:
            try:
                await redis.lpush(
                    USER_MEMORY_QUEUE_KEY,
                    json.dumps(
                        {
                            "user_uid": owner_user_uid,
                            "trigger_at": now_ts,
                        }
                    ),
                )
                await redis.set(
                    last_key,
                    str(now_ts),
                    ex=idle_seconds * 2,
                )
                logger.info(
                    "memory_worker 觸發 user 聚合 user=%s",
                    owner_user_uid,
                )
            except Exception as exc:
                logger.warning(
                    "memory_worker 推入 user_memory_queue 失敗 user=%s: %s",
                    owner_user_uid,
                    exc,
                )
